//! The run adapter's provider side (INTERFACE 6): the HTTP/1.1 transport to
//! the Messages API, request assembly by splicing pinned bytes, tolerant
//! response decoding, and the pure accounting, limit and retry rules.
//!
//! The loop drives one request at a time:
//!
//! 1. build the body from the arrangement's pinned bytes and the appended
//!    messages ([`request`]), and capture it;
//! 2. send it with an [`transport::AbortHandle`] the watcher can fire
//!    ([`transport::Client::send`]);
//! 3. classify the attempt ([`response::classify`]);
//! 4. charge it against the allowances ([`policy::charge`], `usage`);
//! 5. decide whether to use the response, retry or end ([`policy`]).
//!
//! Nothing here touches the archive. Captures, records and the log belong to
//! the loop, which writes the raw bytes this module returns before anything
//! decodes them.
//!
//! Layout:
//! - `url`: the provider base URL and the proxy setting (6.1).
//! - `tls`: the TLS client configuration and, in test builds, extra roots.
//! - `http`: request head, response framing and the recorded header subset.
//! - `transport`: connections, the CONNECT tunnel, timeouts and abort.
//! - `request`: the pinned arrangement and the messages of a placement (4.5, 6.2).
//! - `tolerant`: the tolerant JSON scanner for provider bodies.
//! - `response`: message and error body decoding, attempt classification (6.2, 6.6).
//! - `policy`: charges, retry decisions and the step after a response (6.3–6.6).
//! - `placement`: the loop of one placement (6.3), driving the above.
//! - `stop`: the close watcher and signal handling (6.8).

pub mod http;
pub mod placement;
pub mod policy;
pub mod request;
pub mod response;
pub mod stop;
pub mod tls;
mod tolerant;
pub mod transport;
pub mod url;

pub use tolerant::{Member, Span};

/// An attempt outcome (INTERFACE 6.6, `provider_attempt.outcome`).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Outcome {
    /// HTTP 200 with a decodable message.
    Response,
    /// HTTP 200 whose body is not a decodable message, was cut off or exceeds 32 MiB.
    ResponseUndecodable,
    /// Any other status; its body is captured.
    HttpError,
    /// No complete response within the request timeout.
    Timeout,
    /// Resolution, connection, proxy CONNECT or TLS failed before any request byte was written.
    ConnectionFailed,
    /// The connection failed after request bytes were written and before a status line.
    ConnectionLost,
    /// The close watcher shut the connection down (6.8).
    AbortedByClose,
    /// A signal shut the connection down (6.8).
    AbortedBySignal,
}

impl Outcome {
    pub fn as_str(self) -> &'static str {
        match self {
            Outcome::Response => "response",
            Outcome::ResponseUndecodable => "response_undecodable",
            Outcome::HttpError => "http_error",
            Outcome::Timeout => "timeout",
            Outcome::ConnectionFailed => "connection_failed",
            Outcome::ConnectionLost => "connection_lost",
            Outcome::AbortedByClose => "aborted_by_close",
            Outcome::AbortedBySignal => "aborted_by_signal",
        }
    }
}

/// Why the stop path aborted a request (6.8).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StopCause {
    /// The watcher saw `close_requested`.
    Close,
    /// SIGTERM, SIGINT or SIGHUP before a seal.
    Signal,
}

/// How a placement ends (INTERFACE 6.5, `run_ended.ending` and `cause`).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Ending {
    Sealed,
    EndedUnsubmitted,
    LimitReached,
    StoppedByClose,
    Damaged,
    Interrupted(Cause),
}

/// The cause of an `interrupted` ending.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Cause {
    Signal,
    ProviderUnavailable,
    ProviderRejected,
    ContextExhausted,
    ProviderRefusal,
    MaxTokens,
    ProtocolAnomaly,
    ArchiveWriteFailed,
    ProcessGone,
}

impl Cause {
    pub fn as_str(self) -> &'static str {
        match self {
            Cause::Signal => "signal",
            Cause::ProviderUnavailable => "provider_unavailable",
            Cause::ProviderRejected => "provider_rejected",
            Cause::ContextExhausted => "context_exhausted",
            Cause::ProviderRefusal => "provider_refusal",
            Cause::MaxTokens => "max_tokens",
            Cause::ProtocolAnomaly => "protocol_anomaly",
            Cause::ArchiveWriteFailed => "archive_write_failed",
            Cause::ProcessGone => "process_gone",
        }
    }
}

impl Ending {
    /// The recorded `ending` value.
    pub fn as_str(self) -> &'static str {
        match self {
            Ending::Sealed => "sealed",
            Ending::EndedUnsubmitted => "ended_unsubmitted",
            Ending::LimitReached => "limit_reached",
            Ending::StoppedByClose => "stopped_by_close",
            Ending::Damaged => "damaged",
            Ending::Interrupted(_) => "interrupted",
        }
    }

    /// The recorded `cause`: present only for `interrupted`.
    pub fn cause(self) -> Option<Cause> {
        match self {
            Ending::Interrupted(c) => Some(c),
            _ => None,
        }
    }

    /// Whether `run` may continue the audit after this ending (6.5). An
    /// `interrupted` placement may be continued while authoring has not ended
    /// by other means, such as a seal; that check is the caller's.
    pub fn may_continue(self) -> bool {
        matches!(self, Ending::Interrupted(_))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn recorded_values_match_appendix_a() {
        let outcomes = [
            Outcome::Response,
            Outcome::ResponseUndecodable,
            Outcome::HttpError,
            Outcome::Timeout,
            Outcome::ConnectionFailed,
            Outcome::ConnectionLost,
            Outcome::AbortedByClose,
            Outcome::AbortedBySignal,
        ];
        let names: Vec<&str> = outcomes.iter().map(|o| o.as_str()).collect();
        assert_eq!(
            names,
            [
                "response",
                "response_undecodable",
                "http_error",
                "timeout",
                "connection_failed",
                "connection_lost",
                "aborted_by_close",
                "aborted_by_signal"
            ]
        );
        let causes = [
            Cause::Signal,
            Cause::ProviderUnavailable,
            Cause::ProviderRejected,
            Cause::ContextExhausted,
            Cause::ProviderRefusal,
            Cause::MaxTokens,
            Cause::ProtocolAnomaly,
            Cause::ArchiveWriteFailed,
            Cause::ProcessGone,
        ];
        let names: Vec<&str> = causes.iter().map(|c| c.as_str()).collect();
        assert_eq!(
            names,
            [
                "signal",
                "provider_unavailable",
                "provider_rejected",
                "context_exhausted",
                "provider_refusal",
                "max_tokens",
                "protocol_anomaly",
                "archive_write_failed",
                "process_gone"
            ]
        );
        assert_eq!(Ending::Sealed.as_str(), "sealed");
        assert_eq!(Ending::EndedUnsubmitted.as_str(), "ended_unsubmitted");
        assert_eq!(Ending::LimitReached.as_str(), "limit_reached");
        assert_eq!(Ending::StoppedByClose.as_str(), "stopped_by_close");
        assert_eq!(Ending::Damaged.as_str(), "damaged");
        let i = Ending::Interrupted(Cause::Signal);
        assert_eq!(
            (i.as_str(), i.cause()),
            ("interrupted", Some(Cause::Signal))
        );
        assert_eq!(Ending::Sealed.cause(), None);
        assert!(i.may_continue());
        assert!(!Ending::LimitReached.may_continue());
    }
}

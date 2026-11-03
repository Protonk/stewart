def deliver(reminder, store, gateway):
    if store.was_sent(reminder.id):
        return
    gateway.send(reminder.recipient, reminder.text)
    store.mark_sent(reminder.id)

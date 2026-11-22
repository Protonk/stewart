def deliver(reminder, store, gateway):
    if store.was_sent(reminder.id):
        return
    store.mark_sent(reminder.id)
    gateway.send(reminder.recipient, reminder.text)

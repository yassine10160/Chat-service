
import nats_client

@nats_client.register
def new_message(message: str):
    print(message)

@nats_client.register
def get_year_from_date(date: str):
    return date.year

@nats_client.register('get_current_time')
def current_time():
    return datetime.datetime.now().strftime('%H:%M')

# jetStream
@nats_client.register(js=True)
def new_message(message: str):
    print(message)

@nats_client.register(namespace='UserProfile', js='True')
def new_message_from_userprofile(message: str):
    print(message)
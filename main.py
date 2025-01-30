import time
import telebot
import logging
import calendar
import threading
from config import *
from bson import ObjectId
from language_config import *
from pymongo import MongoClient
from telebot.util import quick_markup
from datetime import datetime, timedelta


logging.basicConfig(level=logging.INFO, filename=LOG_FILE, filemode="a", encoding='utf-8', format="%(asctime)s %(levelname)s %(message)s")

bot = telebot.TeleBot(TG_API_KEY)

client = MongoClient(MONGO_HOST, 27017, username= MONGO_LOGIN, password= MOGO_PASS)
db = client.tg_reminder
users_collection = db.users
reminders_collection = db.reminders

select_hour_markup = {}
select_day_markup = {}
select_language_markup = {}

for i in range(24):
    select_hour_markup[str(i).zfill(2) + ':00'] = {'callback_data': str(i)}

for i in range(31):
    select_day_markup[str(i+1)] = {'callback_data': str(i+1)}

for i in AVAILABLE_LANGUAGES.keys():
    select_language_markup[AVAILABLE_LANGUAGES[i]] = {'callback_data': i}

select_hour_markup = quick_markup(select_hour_markup, row_width= 4)
select_day_markup = quick_markup(select_day_markup, row_width= 4)
select_language_markup = quick_markup(select_language_markup, row_width= 2)


def generate_action_markup(language_code):
    action_markup = {
        ADD_REMINDER[language_code]: {'callback_data': 'add_reminder'},
        DELETE_REMINDER[language_code]: {'callback_data': 'del_reminder'},
        SEE_REMINDER[language_code]: {'callback_data': 'see_reminder'},
    }

    return quick_markup(action_markup, row_width= 1)


def generate_is_repeatable_markup(language_code):
    is_repeatable_markup = {
        SELECT_YES[language_code]: {'callback_data': 'yes'},
        SELECT_NO[language_code]: {'callback_data': 'no'},
    }

    return quick_markup(is_repeatable_markup, row_width= 2)


def generate_repeat_step_markup(language_code):
    repeat_step_markup = {
        ONE_WEEK[language_code]: {'callback_data': 'one_week'},
        ONE_MONTH[language_code]: {'callback_data': 'one_month'},
        ONE_YEAR[language_code]: {'callback_data': 'one_year'},
        SELF_VALUE[language_code]: {'callback_data': 'self_value'},
    }
    return quick_markup(repeat_step_markup, row_width=1)

def generate_delete_markup(user_id):
    delete_markup = {}

    for document in reminders_collection.find({'user_id': user_id}):
        delete_markup[document['description']] = {'callback_data': str(document['_id'])}

    return quick_markup(delete_markup, row_width=1)


def check_reminder():
    while True:
        now = datetime.now(TIMEZONE)
        for document in reminders_collection.find():
            if now.timetuple()[:4] == document['send_time'].timetuple()[:4]:
                if document['is_repeatable']:
                    if document['repeatability_step'] == 'one_week':
                        dt_new = document['send_time'] + timedelta(weeks=1)

                    elif document['repeatability_step'] == 'one_month':
                        next_month = now.month + 1
                        next_year = now.year

                        if next_month > 12:
                            next_month = 1
                            next_year += 1

                        days_in_next_month = calendar.monthrange(next_year, next_month)[1]

                        if document['select_day'] > days_in_next_month:
                            next_day = days_in_next_month
                        else:
                            next_day = document['select_day']

                        dt_new = datetime(next_year, next_month, next_day, hour=document['send_time'].hour)

                    elif document['repeatability_step'] == 'one_year':
                        dt_new = document['send_time'] + timedelta(days=365) # TODO: Переписать чтобы стакалось с високсоными годами

                    else:
                        dt_new = document['send_time'] + timedelta(days=document['repeatability_step'])

                    query_filter = {'_id': document['_id']}
                    update_operation = {'$set':
                                            {'send_time': dt_new, }
                                        }
                    users_collection.update_one(query_filter, update_operation)

                else:
                    reminders_collection.delete_one({
                        '_id': document['_id'],
                    })

            user_document = users_collection.find_one({'_id': document['chat_id']})

            bot.send_message(chat_id=document['chat_id'],
                             text=SEND_REMINDER[user_document['language']]+document['description'],)

        now_time = datetime.now(TIMEZONE)
        seconds_until_next_hour = (60 - now_time.minute) * 60 - now_time.second

        time.sleep(seconds_until_next_hour)




@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    bot.send_message(chat_id= message.chat.id,
                     text= f"Привет, {message.from_user.first_name}, добро пожаловать в бота напоминалку:)")

    bot.send_message(chat_id= message.chat.id,
                     text= f"Выбери язык на котором хочешь общаться со мной из списка",
                     reply_markup=select_language_markup)

    try:
        users_collection.insert_one({
            '_id': message.from_user.id,
            'username': message.from_user.username,
            'chat_status': 'language_select',
            'language': DEFAULT_LANGUAGE,
        })

        logging.info(f'New user added: {message.from_user.username}')

    except:
        pass


@bot.message_handler(content_types= ['text'])
def handle_messages(message):
    user = users_collection.find_one({'_id': message.from_user.id})

    if user['chat_status'] == 'write_description':
        bot.send_message(chat_id= message.chat.id,
                         text= SELECT_DAY[user['language']],
                         reply_markup= select_day_markup)

        res = reminders_collection.insert_one({
            'description': message.text,
            'user_id': message.chat.id,
            'send_time': None,
            'repeatability': None,
            'repeatability_step': None,
            'select_day': None
        })

        query_filter = {'_id': message.from_user.id}
        update_operation = {'$set':
                                {'chat_status': 'choose_day',
                                 'select_id': res.inserted_id}
                            }
        users_collection.update_one(query_filter, update_operation)

    elif user['chat_status'] == 'count_repeat':
        if message.text.isdigit():
            query_filter = {'_id': user['select_id']}
            update_operation = {'$set':
                                    {'repeatability_step': int(message.text),}
                                }

            reminders_collection.update_one(query_filter, update_operation)

            query_filter = {'_id': message.chat.id}
            update_operation = {'$set':
                                    {'chat_status': None,
                                     'select_id': None}
                                }

            users_collection.update_one(query_filter, update_operation)

            bot.send_message(chat_id=message.chat.id,
                             text=END_CREATION_REMINDER[user['language']], )

            bot.send_message(chat_id=message.chat.id,
                             text=ACTION_SELECT[user['language']],
                             reply_markup=generate_action_markup(user['language']))

            logging.info(f'New reminder added - {user['select_id']}')

        else:
            bot.send_message(chat_id=message.chat.id,
                             text=DONT_NUMBER[user['language']],)


    else:
        bot.send_message(chat_id=message.chat.id,
                         text=IDK_WHAT_YOU_WANT[user['language']],
                         reply_markup=generate_action_markup(user['language']))


@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.message:
        user = users_collection.find_one({'_id': call.from_user.id})


        if call.data == 'add_reminder':
            query_filter = {'_id': call.from_user.id}
            update_operation = {'$set':
                                    {'chat_status': 'write_description', }
                                }

            users_collection.update_one(query_filter, update_operation)

            bot.send_message(chat_id= call.from_user.id,
                             text= WRITE_DESCRIPTION[user['language']],)

        elif call.data == 'del_reminder':
            query_filter = {'_id': call.from_user.id}
            update_operation = {'$set':
                                    {'chat_status': 'choose_reminder_to_delete', }
                                }

            users_collection.update_one(query_filter, update_operation)

            bot.send_message(chat_id=call.from_user.id,
                             text=CHOOSE_DELETE_REMINDER[user['language']],
                             reply_markup=generate_delete_markup(call.from_user.id))

        elif call.data == 'see_reminder':
            res = ''
            for document in reminders_collection.find({'user_id': call.from_user.id}):
                res += document['description'] + document['send_time'].strftime(" %Y.%m.%d %H:00") + '\n'

            bot.send_message(chat_id=call.from_user.id,
                             text=SEE_REMINDER_TEXT[user['language']] + res,)

            bot.send_message(chat_id=call.from_user.id,
                             text=ACTION_SELECT[user['language']],
                             reply_markup=generate_action_markup(user['language']))

        elif user['chat_status'] == 'choose_reminder_to_delete':
            reminders_collection.delete_one({'_id': ObjectId(call.data)})

            bot.send_message(chat_id=call.from_user.id,
                             text=COMPLETE_DEL_REMINDER[user['language']])

            bot.send_message(chat_id=call.from_user.id,
                             text=ACTION_SELECT[user['language']],
                             reply_markup=generate_action_markup(user['language']))

        elif user['chat_status'] == 'language_select':
            query_filter = {'_id': call.from_user.id}
            update_operation = {'$set':
                                    {'chat_status': None,
                                     'language': call.data}
                                }

            users_collection.update_one(query_filter, update_operation)

            bot.send_message(chat_id= call.from_user.id,
                             text= ACTION_SELECT[call.data],
                             reply_markup= generate_action_markup(call.data))


        elif user['chat_status'] == 'choose_day':
            day = datetime.now(TIMEZONE).day
            year = datetime.now(TIMEZONE).year
            reminder_day = int(call.data)
            reminder_month = datetime.now(TIMEZONE).month

            if reminder_day <= day:
                reminder_month += 1
                if reminder_month > 12:
                    year += 1
                    reminder_month = 1

                days_in_month = calendar.monthrange(year, reminder_month)[1]

                if reminder_day > calendar.monthrange(year, reminder_month)[1]:
                    reminder_day = days_in_month

            else:
                days_in_month = calendar.monthrange(year, reminder_month)[1]

                if reminder_day > days_in_month:
                    reminder_day = days_in_month

            query_filter = {'_id': user['select_id']}
            update_operation = {'$set':
                                    {'send_time': datetime(year, reminder_month, reminder_day),
                                     'select_day': int(call.data)}
                                }

            reminders_collection.update_one(query_filter, update_operation)

            query_filter = {'_id': call.from_user.id}
            update_operation = {'$set':
                                    {'chat_status': 'choose_time',}
                                }

            users_collection.update_one(query_filter, update_operation)

            bot.send_message(chat_id=call.from_user.id,
                             text=SELECT_HOUR[user['language']],
                             reply_markup=select_hour_markup)

        elif user['chat_status'] == 'choose_time':
            reminder = reminders_collection.find_one({'_id': user['select_id']})

            query_filter = {'_id': user['select_id']}
            update_operation = {'$set':
                                    {'send_time': reminder['send_time'].replace(hour= int(call.data)),}
                                }

            reminders_collection.update_one(query_filter, update_operation)

            query_filter = {'_id': call.from_user.id}
            update_operation = {'$set':
                                    {'chat_status': 'is_repeatable', }
                                }

            users_collection.update_one(query_filter, update_operation)

            bot.send_message(chat_id=call.from_user.id,
                             text=IS_REPEATABLE[user['language']],
                             reply_markup=generate_is_repeatable_markup(user['language']))

        elif user['chat_status'] == 'is_repeatable':
            query_filter = {'_id': user['select_id']}
            update_operation = {'$set':
                                    {'repeatability': True if call.data == 'yes' else False}
                                }

            reminders_collection.update_one(query_filter, update_operation)

            if call.data == 'yes':
                query_filter = {'_id': call.from_user.id}
                update_operation = {'$set':
                                        {'chat_status': 'select_repeat_step', }
                                    }

                users_collection.update_one(query_filter, update_operation)

                bot.send_message(chat_id=call.from_user.id,
                                 text=SELECT_REPEAT_STEP[user['language']],
                                 reply_markup=generate_repeat_step_markup(user['language']))

            elif call.data == 'no':
                query_filter = {'_id': call.from_user.id}
                update_operation = {'$set':
                                        {'chat_status': None,
                                         'select_id': None}
                                    }

                users_collection.update_one(query_filter, update_operation)

                bot.send_message(chat_id=call.from_user.id,
                                 text=END_CREATION_REMINDER[user['language']], )

                bot.send_message(chat_id=call.from_user.id,
                                 text=ACTION_SELECT[user['language']],
                                 reply_markup=generate_action_markup(user['language']))

                logging.info(f'New reminder added - {user['select_id']}')

        elif user['chat_status'] == 'select_repeat_step':
            if call.data == 'one_week' or call.data == 'one_month' or call.data == 'one_year':
                query_filter = {'_id': user['select_id']}
                update_operation = {'$set':
                                        {'repeatability_step': call.data, }
                                    }

                reminders_collection.update_one(query_filter, update_operation)

                query_filter = {'_id': call.from_user.id}
                update_operation = {'$set':
                                        {'chat_status': None,
                                         'select_id': None}
                                    }

                users_collection.update_one(query_filter, update_operation)

                bot.send_message(chat_id=call.from_user.id,
                                 text=END_CREATION_REMINDER[user['language']], )

                bot.send_message(chat_id=call.from_user.id,
                                 text=ACTION_SELECT[user['language']],
                                 reply_markup=generate_action_markup(user['language']))

                logging.info(f'New reminder added - {user['select_id']}')

            else:
                query_filter = {'_id': call.from_user.id}
                update_operation = {'$set':
                                        {'chat_status': 'count_repeat', }
                                    }

                users_collection.update_one(query_filter, update_operation)

                bot.send_message(chat_id=call.from_user.id,
                                 text=COUNT_DAY_TO_REPEAT[user['language']],)



a = threading.Thread(target=check_reminder, name= 'reminder_checker').start()

while True:
    try:
        bot.infinity_polling()
    except Exception as err:
        logging.error(f'Error in polling - {err}')

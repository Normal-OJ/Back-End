'''
create users from a .csv or .json file and
automatically activate them.
each row or object sholud have below keys:
- username
- password
- email
and can bring these optional keys:
- displayedName
- bio
- role
'''

import sys
import json
import csv
from mongo import *
from pathlib import Path

if __name__ == '__main__':
    # check parameter
    if len(sys.argv) < 2:
        print(f'Usage: python {__file__} <user data path>')
        exit(0)
    # read user data
    user_data = Path(sys.argv[1])
    if user_data.suffix == '.json':
        user_data = json.load(user_data.open())
    elif user_data.suffix == '.csv':
        user_data = [*csv.DictReader(user_data.open())]
    else:
        print('Unknown file extension! only support .json and .csv file.')
        exit(0)
    for ud in user_data:
        # signup new user
        u = User.signup(
            username=ud['username'],
            password=ud['password'],
            email=ud['email'],
        )
        # activate account
        # and update profile
        u.activate({
            'displayedName': ud.get('displayedName', ''),
            'bio': ud.get('bio', ''),
        })
        # update user role if needed
        # default value is 2
        if ud.get('role'):
            u.update(role=ud['role'])

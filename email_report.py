#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
asana-stats: Generate progress report based from Asana tasks
Copyright (C) 2012  Diederik van Liere, Wikimedia Foundation

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

import smtplib
import pyasana
from email.message import Message
from cStringIO import StringIO
from datetime import datetime, timedelta

from config import API_KEY, gmail_user, gmail_pwd

def parse_timestamp(timestamp):
    timestamp = timestamp[:-5]
    return datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S')

def parse_tasks(api, tasks):
    data = []
    for task in tasks:
        task = api.get_task(task.id)
        if task.completed:
            if not task.name.endswith(':'):
                if task_finished_in_last_week(task) == True:
                    data.append(task)
    return data


def sort_tasks(tasks):
    pass

def task_finished_in_last_week(task):
    today = datetime.today()
    dt = timedelta(days=7)
    task.completed_at = parse_timestamp(task.completed_at)
    if (today - task.completed_at) < dt:
        return True
    else:
        return False

def generate_subject():
    today = datetime.today()
    last_week = today - timedelta(days=7)
    date = '%s/%s/%s - %s/%s/%s' % (last_week.year, last_week.month, last_week.day, today.year, today.month, today.day)
    subject = 'Analytics Team Status update %s' % date
    return subject

def send_email(email_msg, subject):
    to = ['dvanliere@wikimedia.org','robla@wikimedia.org','dsc@wikimedia.org','aotto@wikimedia.org', 'hfung@wikimedia.org']
    msg = Message()
    msg.add_header('From', 'Diederik van Liere <dvanliere@wikimedia.org>')
    for t in to:
        msg.add_header('To', t)
    msg.add_header('Subject', subject)
    msg.set_payload(email_msg.getvalue())
    mailer = smtplib.SMTP("smtp.gmail.com", 587)
    mailer.ehlo()
    mailer.starttls()
    mailer.ehlo()
    mailer.login(gmail_user, gmail_pwd)
    mailer.sendmail('dvanliere@wikimedia.org', to, msg.as_string())

    # Should be mailer.quit(), but that crashes...
    mailer.close()


def write_header(email_msg):
    #email_msg.write('PLEASE LET ME KNOW IF YOU RECEIVE THIS UPDATE, BY QUICKLY REPLYING "GOT IT".\n\n)
    email_msg.write('This is the weekly automatic update from the Analytics Team. Last week we finished the following tasks (grouped by project).\n')
    email_msg.write('If you think that your progress is under-reported then please start using Asana more frequently.\n')
    email_msg.write('\n')

def write_footer(email_msg):
    email_msg.write('\n')
    email_msg.write('Keep those bean counters running!\n')
    email_msg.write('\n\n')
    email_msg.write('Best,\n')
    email_msg.write('Diederik')

def main():
    email_msg = StringIO()
    write_header(email_msg)
    subject = generate_subject()
    api = pyasana.Api(API_KEY)
    workspaces = api.get_workspaces()
    email_msg.write('%s\n' % subject)
    for workspace in workspaces:
        projects = api.get_projects(workspace.id)
        for project in projects:
            if project.name != 'nourishment':
                tasks = api.get_tasks(project=project.id)
                data = parse_tasks(api, tasks)
                if data:
                    email_msg.write('===%s===\n' % project.name)
                    print '===%s===' % project.name
                for task in data:
                    email_msg.write('* %s completed by %s on %s\n\n' % (task.name, task.assignee, task.completed_at))
                    print task.assignee, task.name
        email_msg.write('\n')
    
    write_footer(email_msg)
    print email_msg.getvalue()
    send_email(email_msg, subject)
            
                
if __name__ == '__main__':
    main()

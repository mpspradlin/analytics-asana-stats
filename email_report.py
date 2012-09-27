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

from wiki_report import write_weekly_wiki_update
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
    dt = timedelta(days=8)
    task.completed_at = parse_timestamp(task.completed_at)
    if (today - task.completed_at) < dt:
        return True
    else:
        return False

def parse_project(project):
    ignore = ['nourishment','Misc Evan']
    for ig in ignore:
        if project.name == ig:
            return False
    return True

def parse_engineer(task):
    ignore = ['Evan Rosen', 'Jessie Wild']
    for ig in ignore:
        if task.assignee == ig:
            return False
    return True    

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
    analytics_progress = StringIO()
    write_header(analytics_progress)
    personal_progress = StringIO()
    
    subject = generate_subject()
    api = pyasana.Api(API_KEY)
    workspaces = api.get_workspaces()
    analytics_progress.write('%s\n' % subject)
    for workspace in workspaces:
        projects = api.get_projects(workspace.id)
        for project in projects:
            if parse_project(project):
                tasks = api.get_tasks(project=project.id)
                data = parse_tasks(api, tasks)
                if data:
                    analytics_progress.write('===%s===\n' % project.name)
                    print '===%s===' % project.name
                for task in data:
                    completed_task = '* %s completed by %s on %s\n\n' % (task.name, task.assignee, task.completed_at)
                    if parse_engineer(task):
                        analytics_progress.write(completed_task)
                        print task.assignee, task.name
                    if task.assignee == 'Diederik van Liere':
                        personal_progress.write(completed_task)
        analytics_progress.write('\n')
    
    write_footer(analytics_progress)
    print analytics_progress.getvalue()
    #send_email(analytics_progress, subject)
    write_weekly_wiki_update(subject, analytics_progress.getvalue() , report_type='weekly')
    
def test():
    title = 'Analytics Team Status update 2012/7/3 - 2012/7/10'
    msg = '''
    Analytics Team Status update 2012/7/3 - 2012/7/10
        ===Limn===
        * Create library entry point, config & API completed by David Schoonover on 2012-07-10 17:15:13
        
        * Create node Middleware for Limn completed by David Schoonover on 2012-07-10 17:18:14
        
        * Update Server to use Middleware completed by David Schoonover on 2012-07-10 17:18:17
        
        * Move Coco source from /lib to /src completed by David Schoonover on 2012-07-10 17:16:51
        
        * Create build task to compile Coco /src to JS /lib completed by David Schoonover on 2012-07-10 17:16:53
        
        * Prune git history to eliminate the 140MB of useless CSVs that snuck in back in commit #5 completed by David Schoonover on 2012-07-10 17:16:50
        
        ===Kraken===
        * Review lucene + scribe changes with Peter Y. completed by Andrew Otto on 2012-07-10 19:17:30
        
        * Confirm boson particle existence completed by David Schoonover on 2012-07-10 17:21:58
        
        * Document architecture Kraken Pixel Service completed by David Schoonover on 2012-07-10 17:49:31
        
        * Research best way to put scribe in prod cluster soon.  Nginx?  Lucen logs? completed by Andrew Otto on 2012-07-10 13:57:26
        
        ===udp2log / udp-filter / webstatscollector===
        * Repackage lucene-search-2 with scribe logging. completed by Andrew Otto on 2012-07-10 13:57:17
        
        * Create debs for scribe + java for Lucene logging. completed by Andrew Otto on 2012-07-10 13:57:18
        
        ===Reportcard===
        * Update node to 0.8.x on kripke completed by Andrew Otto on 2012-07-10 17:37:03
        
        * Prepare July Metrics Meeting completed by Diederik van Liere on 2012-07-10 17:23:47
        
        * WONTFIX Replace boostrip with WMF's agora (https://github.com/munaf/agora) completed by Diederik van Liere on 2012-07-10 17:32:03
        
        ===Servers & Configuration===
        * Configure udp-filter for Grameenphone Bangladesh completed by Andrew Otto on 2012-07-10 17:06:57
        
        * Figure out how the Mayans predicted the Leap Second Apocalypse completed by Andrew Otto on 2012-07-10 13:58:01
        
        * Create MySQL read-only account for Global Dev completed by Diederik van Liere on 2012-07-10 19:49:31
        
        ===Gerrit-stats===
        * Create `analytics/gerrit-stats/data` repo in gerrit completed by Andrew Otto on 2012-07-10 17:45:43
        
        * Add query to count number of commits per day per project completed by Diederik van Liere on 2012-07-10 17:22:39
        
        * Reconstruct datasets for the past completed by Diederik van Liere on 2012-07-10 17:22:34
        
        * Add support for adding new queries completed by Diederik van Liere on 2012-07-10 17:22:47
        
        * Add self-review metric completed by Diederik van Liere on 2012-07-10 17:22:48
        
        ===Devicemap===
        * Discussion with Browserscope project (Adobe, Apache, Facebook, Google) completed by Diederik van Liere on 2012-07-02 18:22:59
        
        ===Misc Diederik===
        * Write self-review completed by Diederik van Liere on 2012-07-03 16:40:12
        
        * Write personal goals completed by Diederik van Liere on 2012-07-03 16:40:26
        
        ===Global Dev Dashboard===
        * I moved all tasks to Reportcard completed by Diederik van Liere on 2012-07-02 22:30:48
        '''
    write_weekly_wiki_update(title, msg, report_type='weekly')
           
                
if __name__ == '__main__':
    main()
    #test()

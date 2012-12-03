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

import sys
import requests
import socket
import smtplib
import logging

from functools import partial
from email.message import Message

log = logging.getLogger()

class Sender(object):
    def __init__(self, username, password, subject, status, verbose, dryrun):
        self.username = username
        self.password = password
        self.subject = subject
        self.status = status
        self.verbose = verbose
        self.dryrun = dryrun

class Email(Sender):
    def __init__(self, server, sender, recipients, subject, status, verbose, dryrun, projects):
        super(Email, self).__init__(server.get('username'), server.get('password'), subject, status, verbose, dryrun)
        self.name = sender.get('name')
        self.email = sender.get('email')
        self.host = server.get('host')
        self.port = server.get('port')
        self.recipients = recipients

    def send(self, url):
        msg = Message()
        msg.add_header('From', '%s %s' % (self.name, self.email))
        for to in self.recipients:
            msg.add_header('To', to)
        msg.add_header('Subject', self.subject)
        msg.set_payload(self.status.getvalue())

        try:
            mailer = smtplib.SMTP(self.host, self.port)
        except socket.error, e:
            error = 'Error initializing SMTP host. If you are using localhost, make sure that sendmail is properly configured.\nError message: %s' % e
            log.error(error)
            raise Exception(error)
            sys.exit(-1)
        mailer.ehlo()
        mailer.starttls()
        mailer.ehlo()
        
        if self.dryrun == False:
            if self.host != 'localhost':
                try:
                    mailer.login(self.username, self.password)
                except smtplib.SMTPAuthenticationError, e:
                    raise Exception('The credentials that you provided for host %s are incorrect.\nError message: %s' % (self.host, e))
                    sys.exit(-1)
            log.info('Emailing report...')
            #mailer.sendmail('%s <%s>' % (self.name, self.email), self.recipients, msg.as_string())
        else:
            print 'From: %s <%s>' % (self.name, self.email)
            print 'To: %s' % ' '.join(self.recipients)
            print 'Message: %s' % msg.as_string()
    
        # Should be mailer.quit(), but that crashes...
        mailer.close()
        
    @classmethod
    def is_registrar_for(cls, report_type):
        '''
        Register this class for the Team progress report
        '''
        return report_type == 'email'
    
class Wiki(Sender):
    def __init__(self, username, password, url, projects, subject, status, verbose, dryrun):
        super(Wiki, self).__init__(username, password, subject, status, verbose, dryrun)
        self.base_url = url
        self.projects = projects
        self.format = 'json'
        self.session = requests.session(config={'store_cookies': True}, params={'format': self.format})
        
        self.lgtoken = None
        self.sessionid = None
        self.edittoken = None
    
    def __call__(self):
        self.login()
    
    def __getattr__(self, attr):
        return partial(self.api, action=attr)

    def send(self, title):
        #wiki = Wiki(credentials.get('username'), credentials.get('password'), credentials.get('base_url'))
        self.login()
#        for project, title in self.titles.iteritems():
#           self.create_status(progress, project)
            #if is_published == False:
        published = self.report_has_been_published(title, self.subject)
        if not published:
            if self.dryrun != True:
                log.info('Updating article %s...' % title)
                self.get_token(titles=title, prop='info|revisions', intoken='edit')
                self.edit(title=title, section=0, summary=self.subject, sectiontitle='', text=self.status.getvalue(), token=self.edittoken)
                log.info('Added status update.')
        else:
            print 'Wiki Article: %s' % title
            print 'Text: %s' % self.status.getvalue()     
                
        #wiki.login()
        #wiki.query(titles=credentials.get('title').get('all'), prop='info|revisions', intoken='edit')
        #wiki.edit(title=credentials.get('title').get('all'), section=0, summary=subject, sectiontitle='', text=msg, token=wiki.edittoken)


    # def create_authorization_url(self):
    #     return '%s%s' % (self.base_url, self.authorization_url)
    
    # def create_edit_token_url(self):
    #     return '%s%s&format=%s' % (self.base_url, self.edit_token_url, self.format)    

    def api(self, **kwargs):
        kwargs.update({'lgname': self.username})
        kwargs.update({'lgpassword': self.password})
        try:
            r = self.session.post(self.base_url, params=kwargs)
        except requests.exceptions.ConnectionError, e:
            raise Exception('Difficulties trying to connect to %s. Make sure that this is the correct URL.\nError message: %s, ' % (self.base_url, e))
            sys.exit(-1)
        
        if self.verbose:
            log.info('Mediawiki API results: %s' % r)
            
        if 'login' in r.json:
            data = r.json['login']
            kwargs.update({'lgtoken': data.get('token')})
            r = self.session.post(self.base_url, params=kwargs)
            if 'login' in r.json:
                authenticated = r.json['login']
                self.lgtoken = authenticated.get('lgtoken')
                self.lguserid = authenticated.get('lguserid')
                self.sessionid = authenticated.get('sessionid')
        elif 'get_token' in r.json:
            key = r.json['query']['pages'].keys()[0]
            data = r.json['query']['pages'].get(key)
            self.edittoken = data.get('edittoken')
        elif 'query' in r.json:
            return r.json
#        elif 'edit' in r.json:
#            print r.json
#        else:
#            print r.json
        
    def report_has_been_published(self, title, subject):
        if title.find('Sandbox') > -1:
            return False
        revisions = self.query(titles=title, prop='info|revisions', rvlimit=500)
        pages = revisions.get('query', {}).get('pages', {}).keys()
        for page in pages:
            for revision in revisions.get('query', {}).get('pages', {}).get(page, {}).get('revisions', {}):
                if revision.get('comment', '').find(subject) > -1:
                    return True
        return False
   
    @classmethod
    def is_registrar_for(cls, report_type):
        '''
        Register this class for the Team progress report
        '''
        return report_type == 'wiki'

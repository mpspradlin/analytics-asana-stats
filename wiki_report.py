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

import json
import requests
from functools import partial

#from xml.etree import cElementTree as etree
#from cStringIO import StringIO
#from urllib2 import Request, urlopen, URLError, HTTPError

from config import wiki_credentials


class Wiki(object):
    def __init__(self, url, username, password):
        self.username = username
        self.password = password
        self.base_url = url
        self.format = 'json'
        #self.authorization_url = 'action=login&lgname=%s&lgpassword=%s' % (self.username, self.password)
        self.edit_token_url = 'action=query&prop=info&intoken=edit&titles=Sandbox'
        self.session = requests.session(config={'store_cookies': True}, params={'format': 'json'})
        
        self.lgtoken = None
        self.sessionid = None
        self.edittoken = None
    
    def __call__(self):
        self.login()
    
    def __getattr__(self, attr):
        return partial(self.api, action=attr)

    def create_authorization_url(self):
        return '%s%s' % (self.base_url, self.authorization_url)
    
    def create_edit_token_url(self):
        return '%s%s&format=%s' % (self.base_url, self.edit_token_url, self.format)
    

    def api(self, **kwargs):
        kwargs.update({'lgname': self.username})
        kwargs.update({'lgpassword': self.password})
        r = self.session.post(self.base_url, params=kwargs)
        if 'login' in r.json:
            data = r.json['login']
            kwargs.update({'lgtoken': data.get('token')})
            r = self.session.post(self.base_url, params=kwargs)
            if 'login' in r.json:
                authenticated = r.json['login']
                self.lgtoken = authenticated.get('lgtoken')
                self.lguserid = authenticated.get('lguserid')
                self.sessionid = authenticated.get('sessionid')
        elif 'query' in r.json:
            print r.json
            key = r.json['query']['pages'].keys()[0]
            data = r.json['query']['pages'].get(key)
            self.edittoken = data.get('edittoken')
        elif 'edit' in r.json:
            print r.json
        else:
            print r.json
            
    @classmethod
    def is_registrar_for(cls, report_type):
        '''
        Register this class for the Team progress report
        '''
        return report_type == 'wiki'


def write_weekly_wiki_update(subject, msg, report_type='weekly'):
    subject = '==%s==' % subject
    msg = '%s\n%s' % (subject, msg)
    if report_type == 'weekly':
        credentials = wiki_credentials.get('office')
        wiki = Wiki(credentials.get('username'), credentials.get('password'), credentials.get('base_url'))
        wiki.login()
        wiki.query(titles=credentials.get('title').get('all'), prop='info|revisions', intoken='edit')
        wiki.edit(title=credentials.get('title').get('all'), section=0, summary=subject, sectiontitle='', text=msg, token=wiki.edittoken)
     
        
def write_status_updates():
    for wiki, credentials in wiki_credentials.iteritems():
        wiki = Wiki(credentials.get('username'), credentials.get('password'), credentials.get('base_url'))
        wiki.login()
        wiki.query(titles=credentials.get('title').get('test'), prop='info|revisions', intoken='edit')
        wiki.edit(title=credentials.get('title').get('test'), section=0, summary='', sectiontitle='', text='Foo bar', token=wiki.edittoken)

    
if __name__ == '__main__':
    write_status_updates()
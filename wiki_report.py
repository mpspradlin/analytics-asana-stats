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

from xml.etree import cElementTree as etree
from urllib2 import Request, urlopen, URLError, HTTPError

from config import wiki_credentials


class Wiki(object):
    def __init__(self, username, password, url):
        self.username = username
        self.password = password
        self.url = url
        self.edit_token = self.get_edit_token()
    
    def fetch_url(self, url):
        req = Request(url)
        try:
            response = urlopen(req)
        except HTTPError, e:
            print 'The server couldn\'t fulfill the request.'
            print 'Error code: ', e.code
        except URLError, e:
            print 'We failed to reach a server.'
            print 'Reason: ', e.reason
        return response.read()

    
    def get_edit_token(self):
        data = self.fetch_url(self.url)
        self.parse_edit_token(data)

    def parse_edit_token(self, data):
        xml  = etree.fromstring(data)
        query = xml.findall('query')[0]
        pages = query.findall('pages')
        for page in pages:
            print page.keys(), page.items()
            iterator = page.getiterator()
            for it in iterator:
                print it
            print dir(page), page.find('edittoken')
        
        '''http://en.wikipedia.org/w/api.php?action=query&prop=info&intoken=edit&titles=Sandbox'''
        pass


def test():
    wikis = {}
    for wiki, credentials in wiki_credentials.iteritems():
        wikis[wiki] = Wiki(**credentials)
    
    for wiki_name, wiki in wikis.iteritems():
        wiki.get_edit_token()
    
        
    
if __name__ == '__main__':
    test()
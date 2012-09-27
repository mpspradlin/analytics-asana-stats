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
import sys
import requests
import socket
import smtplib

from functools import partial
from email.message import Message
from cStringIO import StringIO


def make_heading(fn):
	def wrapper(*args, **kwargs):
		format = kwargs.pop('format', None)
		if format == 'wikitext':
			return "==" + fn(*args, **kwargs) + "=="
		else:						
			return fn(*args, **kwargs)
	return wrapper

def make_body(fn):
	def wrapper(*args, **kwargs):
		format = kwargs.pop('format', None)
		if format == 'wikitext':
			return fn(*args, **kwargs)
		else:						
			return fn(*args, **kwargs)
	return wrapper


class Report(object):
	def __init__(self, username, password, output, args):
		self.username = username
		self.password = password
		self.output = output
		self.dryrun = args.dry_run
		self.verbose = args.verbose
		self.data = StringIO()

	@make_heading
	def generate_subject(self, progress):
		return '%s %s/%s/%s - %s/%s/%s' % (progress.name, progress.start_date.year, progress.start_date.month, progress.start_date.day, progress.end_date.year, progress.end_date.month, progress.end_date.day)
	
	@make_body
	def write_body(self, tasks):
		self.data.write('\n\n')
		self.write_header()
		for project in tasks:
			self.data.write('%s\n' % project.name)
			for task in tasks[project]:
				self.data.write('%s\n' % task)
		self.data.write('\n\n')
		self.write_footer()

	def write_header(self):
		fh = open('templates/%s_header.txt' % (self.output), 'r')
		for line in fh:
			self.data.write(line)
		fh.close()
	
	def write_footer(self):
		fh = open('templates/%s_footer.txt' % (self.output), 'r')
		for line in fh:
			self.data.write(line)
		fh.close()
		


class Email(Report):
	def __init__(self, name, email, recipients, host, port, **kwargs):
		super(Email, self).__init__(**kwargs)
		self.name = name
		self.email = email
		self.host = host
		self.port = port
		self.recipients = recipients


	def send(self, msg):
		try:
			mailer = smtplib.SMTP(self.host, self.port)
		except socket.error, e:
			raise Exception('Error initializing SMTP host. If you are using localhost, make sure that sendmail is properly configured.\nError message: %s' % e)
			sys.exit(-1)
		mailer.ehlo()
		mailer.starttls()
		mailer.ehlo()
		
		if self.dryrun != True:
			if self.host != 'localhost':
				try:
					mailer.login(self.username, self.password)
				except smtplib.SMTPAuthenticationError, e:
					raise Exception('The credentials that you provided for host %s are incorrect.\nError message: %s' % (self.host, e))
					sys.exit(-1)
			print 'mailing...'
			mailer.sendmail('%s <%s>' % (self.name, self.email), msg.as_string())
		else:
			print msg.as_string()
	
		# Should be mailer.quit(), but that crashes...
		mailer.close()
		
	@classmethod
	def is_registrar_for(cls, report_type):
		'''
		Register this class for the Team progress report
		'''
		return report_type == 'email'
	
	def create(self, progress):
		subject = self.generate_subject(progress)
		self.write_body(progress.tasks)

		msg = Message()
		msg.add_header('From', '%s %s' % (self.name, self.email))
		for to in self.recipients:
			msg.add_header('To', to)
		msg.add_header('Subject', subject)
		msg.set_payload(self.data.getvalue())
		self.send(msg)

		if self.verbose and self.dryrun == False:
			self.data.seek(0)
			print self.data.getvalue()

class Wiki(Report):
	def __init__(self, url, titles, **kwargs):
		super(Wiki, self).__init__(**kwargs)
		self.base_url = url
		self.titles = titles
		self.format = 'json'
		self.session = requests.session(config={'store_cookies': True}, params={'format': self.format})
		
		self.lgtoken = None
		self.sessionid = None
		self.edittoken = None
	
	def __call__(self):
		self.login()
	
	def __getattr__(self, attr):
		return partial(self.api, action=attr)


	def create(self, progress):
		#wiki = Wiki(credentials.get('username'), credentials.get('password'), credentials.get('base_url'))
		subject = self.generate_subject(progress, format='wikitext')
		self.data.write(subject)
		self.write_body(progress.tasks, format='wikitext')
		status = self.data.getvalue()
		
		if self.verbose and self.dryrun == False:
			self.data.seek(0)
			print self.data.getvalue()
		
		self.login()
		for project, title in self.titles.iteritems():
			self.query(titles=title, prop='info|revisions', intoken='edit')
			if self.dryrun != True:
				self.edit(title=title, section=0, summary=subject, sectiontitle='', text=status, token=self.edittoken)
			else:
				print 'Title: %s' % title
				print 'Summary: %s' % subject
				print 'Text: %s' % status	 
		
		#wiki.login()
		#wiki.query(titles=credentials.get('title').get('all'), prop='info|revisions', intoken='edit')
		#wiki.edit(title=credentials.get('title').get('all'), section=0, summary=subject, sectiontitle='', text=msg, token=wiki.edittoken)


	# def create_authorization_url(self):
	#	 return '%s%s' % (self.base_url, self.authorization_url)
	
	# def create_edit_token_url(self):
	#	 return '%s%s&format=%s' % (self.base_url, self.edit_token_url, self.format)	

	def api(self, **kwargs):
		kwargs.update({'lgname': self.username})
		kwargs.update({'lgpassword': self.password})
		try:
			r = self.session.post(self.base_url, params=kwargs)
		except requests.exceptions.ConnectionError, e:
			raise Exception('Difficulties trying to connect to %s. Make sure that this is the correct URL.\nError message: %s, ' % (self.base_url, e))
			sys.exit(-1)

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
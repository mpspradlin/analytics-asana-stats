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

import logging
import pyasana

from cStringIO import StringIO
from sender import Sender

log = logging.getLogger()

def add_wikitext(fn):
	def wrapper(*args, **kwargs):
		output_format = kwargs.pop('output_format', None)
		style_element = kwargs.pop('style_element', None)
		args = list(args)
		if output_format == 'wiki':
			elements = {
					'heading1': '%s%s%s' % ('=', args[1], '='),
					'heading2': '%s%s%s' % ('==', args[1], '=='),
					'heading3': '%s%s%s' % ('===', args[1], '==='),
					}
			args[1] = elements.get(style_element, args[1])
			args = tuple(args)
		return fn(*args, **kwargs) 
	return wrapper


class Report(object):
	def __init__(self, tasks, start_date, end_date, output, frequency, verbose, dryrun):
		self.tasks = tasks
		self.start_date = start_date
		self.end_date = end_date
		self.status = StringIO()
		self.subject = None
		self.output = output
		self.verbose = verbose
		self.frequency = frequency
		self.dryrun = dryrun

	def __str__(self):
		return 'Report for period: %s - %s' % (self.start_date, self.end_date)
	
	def generate_subject(self, project):
		return 'Analytics %s update for %s <%s-%s>' % (self.frequency, project, self.start_date, self.end_date)

	@add_wikitext
	def write_line(self, line):
		self.status.write('%s\n' % line)

	def create_statuses(self):
		for output_format in self.output.keys():
			for project_to_report, url in self.output.get(output_format, {}).get('projects', {}).iteritems():
				self.status = StringIO()
				for date, projects in self.tasks.iteritems():
					if project_to_report == 'All':
						projects = self.tasks.get(date)
					else:
						projects = {}
						key = self.tasks[date].get(project_to_report)
						projects[key] = self.tasks.get(date).get(key)
					
					self.create_status(projects, output_format)
					if self.status.getvalue() != None and self.subject != None: 
						self.send(url)
					#project = pyasana.Project(0, project)
					#projects = [project] if project in self.tasks[date].keys() else []
		
	def create_status(self, projects, output_format):
		for project, tasks in projects.iteritems():
			if tasks != [] and tasks != None:
				self.write_header(output_format)
				self.subject = self.generate_subject(project)
				self.write_line(self.subject, output_format=self.output, style_element='heading1')
					#for project in projects:
						#tasks = data[project]
						#if tasks != []:
				self.write_line(project.name, output_format=self.output, style_element='heading2')
				for task in tasks:
					self.write_line(task, output_format=self.output)
				self.write_footer(output_format)
		
		if self.verbose:
			self.status.seek(0)
			print self.status.getvalue()
	
	def send(self, url):
		for output in self.output.keys():
			classes = Sender.__subclasses__()
			for cls in classes:
				if cls.is_registrar_for(output):
					params = self.output.get(output)
					params['subject'] = self.subject
					params['status'] = self.status
					params['dryrun'] = self.dryrun
					params['verbose'] = self.verbose
					sender = cls(**params)
					sender.send(url)
#		for op in self.output:
#			for cls in Report.__subclasses__():
#				if cls.is_registrar_for(op):
#					params = output.get(op)
#					params['args'] = args
#					params['output'] = op
#					params['start_date'] = self.start_date
#					params['end_date'] = self.end_date
#					cls = cls(**params)
#					setattr(self, op, cls)
#					classes += 1
#		if classes != count:
#			raise ValueError('Could not find all classes to handle output format(s) %s.' % ','.join(self.output))
#			sys.exit(-1)
		
	def write_header(self, output_format):
		fh = open('templates/%s_header.txt' % (output_format), 'r')
		for line in fh:
			self.status.write(line)
		fh.close()
	
	def write_footer(self, output_format):
		fh = open('templates/%s_footer.txt' % (output_format), 'r')
		for line in fh:
			self.status.write(line)
		fh.close()

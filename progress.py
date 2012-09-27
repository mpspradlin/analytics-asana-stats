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

import os
import sys
import pyasana
import calendar
import logging
import argparse
import parsedatetime.parsedatetime as pdt
import parsedatetime.parsedatetime_consts as pdc

from cStringIO import StringIO
from datetime import datetime, timedelta
from time import mktime

from report import Report, Wiki, Email

from yaml import load, dump
try:
	from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
	from yaml import Loader, Dumper

log = logging.getLogger()
log.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
log.addHandler(ch)

ON_POSIX = 'posix' in sys.builtin_module_names

class Logger(object):
	def __init__(self, func):
		self.func = func

	def __get__(self, obj, cls=None):
		return self.__class__(self.func.__get__(obj, cls))

	def __call__(self, *args, **kwargs):
		output = self.func(*args, **kwargs)
		if kwargs != {} and kwargs != None:
			logging.info('Called %s with result: %s and kwargs: %s' % (self.func.__name__, output, ';'.join(['%s=%s' % (key, value) for key, value in kwargs.iteritems()])))
		else:
			logging.info('Called %s with result: %s' % (self.func.__name__, str(output)))
		return output


class Progress(object):
	def __init__(self, name, frequency, ignore_projects, team_members, output, time_frame, asana_api_key, args):
		self.name = name
		self.frequency = frequency
		self.ignore_projects = ignore_projects
		self.team_members = set(team_members)
		self.asana_api_key = asana_api_key
		self.output = output.keys()
		self.verbose = args.verbose
		self.dryrun = args.dry_run
		self.time_frame = time_frame
		self.format_choices = ['wiki', 'email']
		self.frequency_choices = ['weekly', 'monthly']	
		self.tasks = {}
		
		self.validate_input()
		self.start_date, self.end_date = self.construct_time_window()
		self.dt = self.max_age()
		
		self.init_report_class(output, args)

		self.api = pyasana.Api(self.asana_api_key)
		self.workspaces = self.api.get_workspaces()

	def init_report_class(self, output, args):
		count = len(self.output)
		classes=0
		for op in self.output:
			for cls in Report.__subclasses__():
				if cls.is_registrar_for(op):
					params = output.get(op)
					params['args'] = args
					params['output'] = op
					cls = cls(**params)
					setattr(self, op, cls)
					classes+=1
		if classes != count:
			raise ValueError('Could not find all classes to handle output format(s) %s.' % ','.join(self.output))
			sys.exit(-1)
	

	def construct_time_window(self):
		c = pdc.Constants()
		p = pdt.Calendar(c)
		result = p.parse(self.time_frame)
		end_date = datetime.today()
		start_date = datetime.fromtimestamp(mktime(result[0]))
		if (end_date.day - start_date.day) > 7:
			start_date = start_date + timedelta(days=7)
		return start_date, end_date

	def max_age(self):
		if self.frequency == 'weekly':
			return timedelta(days=7)
		elif self.frequency == 'monthly':
			number_of_days_in_month = calendar.monthrange(self.start_date.year,self.start_date.month)[1]
			return timedelta(days=number_of_days_in_month)

	def parse_project(self, project):
		for ig in self.ignore_projects:
			if project.name == ig:
				return False
		return True

	def is_team_member(self, task):
		if task.assignee in self.team_members:
			return True
		else:
			return False

	def parse_timestamp(self, timestamp):
		timestamp = timestamp[:-5]
		return datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S')

	def parse_tasks(self, api, tasks):
		data = []
		for task in tasks:
			task = api.get_task(task.id)
			if task.completed:
				if not task.name.endswith(':'):
					if self.task_finished_during_time_window(task) == True:
						data.append(task)
		return data
	
	def run(self):
		for workspace in self.workspaces:
			projects = self.api.get_projects(workspace.id)
			for project in projects:
				if self.parse_project(project):
					tasks = self.api.get_tasks(project=project.id)
					data = self.parse_tasks(self.api, tasks)
					if any([self.is_team_member(task) for task in data]):
						self.tasks.setdefault(project, [])
					for task in data:
						if self.is_team_member(task):
							completed_task = '* %s completed by %s on %s' % (task.name, task.assignee, task.completed_at)
							self.tasks[project].append(completed_task)


	def send(self):
		for output in self.output:
				report = getattr(self, output)
				report.create(self)

	def task_finished_during_time_window(self, task):
		task.completed_at = self.parse_timestamp(task.completed_at)
		if (self.end_date - task.completed_at) < self.dt:
			return True
		else:
			return False
	
	def validate_input(self):
		for output in self.output:
			if output not in self.format_choices:
				raise Exception('You have specified an invalid output format: %s\nValid choices are: %s' % (self.output, ','.join(self.format_choices)))
				sys.exit(-1)
			if self.frequency not in self.frequency_choices:
				raise Exception('You have specified an invalid frequency: %s.\nValid choices are:' % (self.frequency, ','.join(self.frequency_choices)))
				sys.exit(-1)

	
def flatten(input_dictionary, output_dictionary={}):
	for key, value in input_dictionary.iteritems():
		if type(value) == dict:
			output_dictionary = flatten(value, output_dictionary)
		else:				
			output_dictionary[key] = value
	return output_dictionary


def parse_commandline():
	parser = argparse.ArgumentParser(description='Welcome to asana-stats. The default location for the config.yaml file is ~/.asana-stats.yaml, you can specify an alternative location using the --config option.')
	parser.add_argument('--config', help='Specify the absolute path to tell asana-stats where it can find the config.yaml file', action='store', required=False, default='~/.asana-stats.yaml')
	parser.add_argument('--dry_run', help='This won\'t distribute the status update, primarily for debugging purposes', required=False, default=False, action='store_true')
	parser.add_argument('--verbose', help='Indicate whether to stdout should be turned on.', action='store_true', default=False)
	return parser.parse_args()


def load_configuration(path):
	if path.startswith('~'):
		path = os.path.expanduser(path)
	
	if os.path.exists(path) and path.endswith('yaml'):
		fh = open(path,'r')
		configuration = load(fh, Loader=Loader)
		fh.close()
	else:
		raise Exception('Could not load configuration file %s, please make sure that the path is correct.' % (path))
		sys.exit(-1)
	return configuration


def main():
	args = parse_commandline()
	configuration = load_configuration(args.config)
	reports = [report for report in configuration.get('reports',{}).keys() if report.startswith('report')]
	for report in reports:
		settings = configuration.get('reports',{}).get(report)
		if settings:
			print 'Creating report %s' % report
			settings['output']['email'] = flatten(settings['output'].get('email',{}))
			settings['output']['wiki'] = settings['output'].get('wiki', {})
			#settings['output']['wiki'] = flatten(settings['output'].get('wiki', {}), dict())
			settings['asana_api_key'] = configuration.get('asana_api_key')
			settings['args'] = args
			progress = Progress(**settings)
			progress.run() 
			progress.send()
			print 'DONE'
	
if __name__ == '__main__':
	main()

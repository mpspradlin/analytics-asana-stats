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
import calendar
import logging
import argparse
import dateutil.relativedelta

import pyasana
from datetime import datetime, timedelta, date
from report import Report

from yaml import load
try:
	from yaml import CLoader as Loader
except ImportError:
	from yaml import Loader

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
		self.output = output
		self.verbose = args.verbose
		self.dryrun = True  # args.dry_run
		self.time_frame = time_frame
		self.format_choices = ['wiki', 'email']
		self.frequency_choices = ['weekly', 'monthly']
		self.number_report = int(args.number_reports)	
		self.tasks = {}
		self.create_tasks_dictionary()
		self.validate_input()
		self.start_date = None
		self.end_date = None
		self.set_time_frame()
		# self.dt = self.max_age()
		# self.init_report_class(output, args)
		self.api = pyasana.Api(self.asana_api_key, 100)
		self.workspaces = self.api.get_workspaces()

	def generate_key(self, start_date, end_date):
		if not isinstance(start_date, date) or not isinstance(end_date, date):
			raise Exception('start and end date should be of type date not datetime.')
		else:
			return '%s-%s' % (str(start_date), str(end_date))

	def set_time_frame(self):
		self.start_date = min(self.tasks.keys())
		self.end_date = max(self.tasks.keys())

	def construct_time_window(self, obs_date=date.today(), number=1):
		if self.frequency == 'weekly':
			end_date = obs_date - timedelta(days=obs_date.weekday(), weeks=number - 1)
			start_date = end_date - timedelta(weeks=1)
		elif self.frequency == 'monthly':
			prev_date = obs_date - dateutil.relativedelta.relativedelta(months=number)
			start_date = date(prev_date.year, prev_date.month, 1)
			number_of_days_in_month = calendar.monthrange(start_date.year, start_date.month)[1]
			end_date = date(prev_date.year, prev_date.month, number_of_days_in_month)
		else:
			raise Exception('Frequency %s is not supported.' % self.frequency)
			sys.exit(-1)
		return start_date, end_date	
		
	def create_tasks_dictionary(self):
		for number in xrange(self.number_report):
			number += 1
			start_date, end_date = self.construct_time_window(number=number)
			# key = self.generate_key(start_date, end_date)
			self.tasks.setdefault(start_date, {})

	def task_finished_during_time_window(self, task):
		task.completed_at = self.parse_timestamp(task.completed_at)
		start_date, end_date = self.construct_time_window(task.completed_at)
		if start_date >= self.start_date and end_date <= self.end_date:
			return start_date
		else:
			return None

	def max_age(self):
		if self.frequency == 'weekly':
			return timedelta(days=7)
		elif self.frequency == 'monthly':
			number_of_days_in_month = calendar.monthrange(self.start_date.year, self.start_date.month)[1]
			return timedelta(days=number_of_days_in_month)

	def parse_project(self, project):
		for ig in self.ignore_projects:
			if project.name == ig:
				return False
		return True

	def is_team_member(self, task):
		if task.assignee and task.assignee.name in self.team_members:
			return True
		else:
			return False

	def parse_timestamp(self, timestamp):
		timestamp = timestamp[:-5]
		timestamp = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S')
		return timestamp.date()

	def parse_tasks(self, api, tasks):
		data = {}
		for task in tasks:
			task = api.get_task(task.id)
			if task.completed:
				if not task.name.endswith(':'):
					key = self.task_finished_during_time_window(task)
					if key:
						data.setdefault(key, [])
						data[key].append(task)
		return data
	
	def run(self):
		for workspace in self.workspaces:
			log.info('Workspace: %s' % workspace.name)
			projects = self.api.get_projects(workspace.id)
			if self.dryrun:
				projects = projects[0:4] if len(projects) > 3 else []
			
			for project in projects:
				log.info('Parsing project: %s' % project.name)
				if self.parse_project(project):
					tasks = self.api.get_tasks(project=project.id)
					data = self.parse_tasks(self.api, tasks)
					for date, tasks in data.iteritems():
						if any([self.is_team_member(task) for task in tasks]):
							self.tasks[date].setdefault(project, [])
						for task in tasks:
							if self.is_team_member(task):
								completed_task = '* %s completed by %s on %s' % (task.name, task.assignee.name, task.completed_at)
								log.info('Task: %s' % completed_task)
								self.tasks[date].setdefault(project, [])
								self.tasks[date][project].append(completed_task)

	def create_reports(self):
		report = Report(self.tasks, self.start_date, self.end_date, self.output, self.frequency, self.verbose, self.dryrun)
		report.create_statuses()

	def validate_input(self):
		for output in self.output:
			if output not in self.format_choices:
				raise Exception('You have specified an invalid output format: %s\nValid choices are: %s' % (self.output, ','.join(self.format_choices)))
				sys.exit(-1)
			if self.frequency not in self.frequency_choices:
				raise Exception('You have specified an invalid frequency: %s.\nValid choices are:' % (self.frequency, ','.join(self.frequency_choices)))
				sys.exit(-1)

	
# def flatten(input_dictionary, output_dictionary={}):
# 	for key, value in input_dictionary.iteritems():
# 		if type(value) == dict:
# 			output_dictionary = flatten(value, output_dictionary)
# 		else:				
# 			output_dictionary[key] = value
# 	return output_dictionary


def parse_commandline():
	parser = argparse.ArgumentParser(description='Welcome to asana-stats. The default location for the config.yaml file is ~/.asana-stats.yaml, you can specify an alternative location using the --config option.')
	parser.add_argument('--config', help='Specify the absolute path to tell asana-stats where it can find the config.yaml file', action='store', required=False, default='~/.asana-stats.yaml')
	parser.add_argument('--dry_run', help='This won\'t distribute the status update, primarily for debugging purposes', required=False, default=False, action='store_true')
	parser.add_argument('--verbose', help='Indicate whether logging to stdout should be turned on.', action='store_true', default=False)
	parser.add_argument('--number_reports', help='Indicate how far back in time you want to go for generating reports. ', default=1, required=False, action='store')
	return parser.parse_args()


def load_configuration(path):
	if path.startswith('~'):
		path = os.path.expanduser(path)
	
	if os.path.exists(path) and path.endswith('yaml'):
		fh = open(path, 'r')
		configuration = load(fh, Loader=Loader)
		fh.close()
	else:
		raise Exception('Could not load configuration file %s, please make sure that the path is correct and that the extension of the file is yaml.' % (path))
		sys.exit(-1)
	return configuration


def main():
	args = parse_commandline()
	configuration = load_configuration(args.config)
	reports = [report for report in configuration.get('reports', {}).keys() if report.startswith('report')]
	for report in reports:
		settings = configuration.get('reports', {}).get(report)
		if settings:
			log.info('Creating report %s' % report)
			settings['output']['email'] = settings['output'].get('email', {})
			settings['output']['wiki'] = settings['output'].get('wiki', {})
			settings['asana_api_key'] = configuration.get('asana_api_key')
			settings['args'] = args
			progress = Progress(**settings)
			progress.run() 
			progress.create_reports()
			log.info('Finished creating report %s' % report)
	
if __name__ == '__main__':

	main()

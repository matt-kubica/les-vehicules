from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler
from smtplib import SMTP
from email.mime.text import MIMEText
from email.message import Message
import requests, ssl
import sys, os, time
import logging

logging.basicConfig(level=logging.getLevelName(os.environ.get('LOGGING_LEVEL')))

BASE_URL = os.environ.get('BASE_URL')
URL = BASE_URL + os.environ.get('URL_SUFFIX')


class Vehicle:

	@staticmethod
	def from_div(vehicle_div):
		url_suffix = [x['href'] for x in vehicle_div.div.find_all('a')][0]
		s = [x.string for x in vehicle_div.div.find_all('strong')]
		name, price = s[0], s[1]
		return Vehicle(name, price, url_suffix)

	def __init__(self, name, price, url_suffix):
		self.name = name
		self.price = price if not price == 'Prix sur demande' else '-'
		self.url = BASE_URL + url_suffix

	def __str__(self):
		return ' * Name: {0}\n * Price: {1}\n'.format(
			self.name, self.price)

	def __repr__(self):
		return '<Vehicle {0}>'.format(self.name)

	def __key(self):
		return (self.name, self.price)

	def __hash__(self):
		return hash(self.__key())

	def __eq__(self, other):
		if not isinstance(other, Vehicle):
			return NotImplemented
		return self.__key() == other.__key()




class VehicleFinder:

	def __init__(self):
		self.vehicles, self.key = [], None
		self.scheduler, self.smtp = BackgroundScheduler(), None
		self.authorize()

		cron_params = {
			'hour': os.environ.get('SCHEDULER_CRON_HOUR_TRIGGER'),
			'minute': os.environ.get('SCHEDULER_CRON_MINUTE_TRIGGER'),
		}
		self.scheduler.add_job(**cron_params, trigger='cron', func=self.main_task)


	def authorize(self):
		headers = {
			'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
			'Sec-Fetch-Site': 'cross-site',
			'Sec-Fetch-Mode': 'navigate',
			'Sec-Fetch-Dest': 'iframe',
			'Referer': 'http://www.aap57.fr/',
		}
		
		redirected_url = None
		with requests.get(URL, headers=headers, allow_redirects=False) as res:
			redirected_url = res.headers['Location']
		with requests.get(BASE_URL + redirected_url, allow_redirects=False) as res:
			self.key = res.headers['Location']


	def obtain_vehicles_list(self):
		# go through all pages
		page_num, vehicles = 1, []
		while True:
			soup = None
			url = BASE_URL + self.key + '/page-{0}'.format(page_num)
			with requests.get(url) as res:
				soup = BeautifulSoup(res.content, 'html.parser')

			divs = soup.find_all(attrs={'class': 'parts-element'})
			if len(divs) == 0: break
			for vehicle_div in divs:
				vehicles += [Vehicle.from_div(vehicle_div)]
			page_num += 1
		return vehicles


	def send_notification(self, vehicles):
		try:
			self.smtp = SMTP(os.environ.get('SENDER_EMAIL_HOST'), 
				        	 os.environ.get('SENDER_EMAIL_PORT'))
			self.smtp.ehlo()
			self.smtp.starttls(context=ssl.create_default_context())
			self.smtp.login(os.environ.get('SENDER_EMAIL_ADDRESS'), 
				       		os.environ.get('SENDER_EMAIL_PASSWORD'))
		except Exception as err:
			logging.error('SMTP error: \n{0}'.format(err))
			return
			# exit(1)

		hyperlinks = ''
		for v in vehicles:
			print('{0}\n'.format(v))
			hyperlinks += '<a href="{0}">{1}, {2}</a><br>'.format(
				v.url, v.name, v.price
			)

		message = Message()
		message['Subject'] = os.environ.get('NOTIFICATION_EMAIL_SUBJECT')
		message['From'] = os.environ.get('SENDER_EMAIL_ADDRESS')
		message['To'] = os.environ.get('RECEIVER_EMAIL_ADDRESS')
		message.add_header('Content-Type','text/html')
		message.set_payload(
			'<h3>Znaleziono {0} nowych <i>vehicules</i>!</h3><br>{1}' \
			.format(len(vehicles), hyperlinks)
		)

		with open(os.environ.get('RECEIVER_EMAIL_ADDRESSES_FILE')) as fp:
			receivers = [r.rstrip() for r in fp.readlines()]
			for receiver in receivers:
				self.smtp.sendmail(
					os.environ.get('SENDER_EMAIL_ADDRESS'), 
					receiver, 
					message.as_string().encode('utf8')
				)

	def initialize_vehicles_list(self):
		self.vehicles = self.obtain_vehicles_list()

	def main_task(self):
		logging.info('Vehicles in memory: {0}\nSearching for new ones...'.format(self.vehicles))

		new_vehicles = self.obtain_vehicles_list()
		if not len(new_vehicles):
			logging.info('Couldn\'t find any vehicle, need to authorize...\n')
			self.authorize()
		else:
			logging.info('Found {0} vehicles...\n'.format(len(new_vehicles)))

		unseen_vehicles = list(set(new_vehicles).difference(self.vehicles))
		if unseen_vehicles:
			logging.info('Found {0} unseen vehicles:'.format(len(unseen_vehicles)))
			self.send_notification(unseen_vehicles)
			self.vehicles = new_vehicles


	def start(self):
		self.initialize_vehicles_list()
		self.scheduler.start()
		logging.info('Vehicle Finder initialized...')

		try:
			while True: time.sleep(1)
		except KeyboardInterrupt:
			logging.info('Gracefully stopping...')
			exit(0)
		

if __name__ == '__main__':
	vf = VehicleFinder()
	vf.start()
	

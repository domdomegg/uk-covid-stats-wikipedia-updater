import os
import requests
import csv
import datetime
import re

if not os.environ.get('WIKIPEDIA_BOT_USERNAME'):
    print('Missing WIKIPEDIA_BOT_USERNAME environment variable')
    exit(1)

if not os.environ.get('WIKIPEDIA_BOT_PASSWORD'):
    print('Missing WIKIPEDIA_BOT_PASSWORD environment variable')
    exit(1)

print('Getting latest data...')
date = datetime.date.today().isoformat()
req = requests.get('https://api.coronavirus.data.gov.uk/v1/data?filters=date=' + date + ';areaType=overview&structure=%7B%22areaName%22:%22areaName%22,%22date%22:%22date%22,%22cases%22:%22cumCasesByPublishDate%22,%22deaths%22:%22cumDeathsByPublishDate%22%7D&format=json')

print('Validating request...')
if req.status_code == 204:
    print('Today\'s data has not been published yet')
    exit(0)
elif req.status_code != 200:
    print('Something went wrong getting the data:')
    print(req.text)
    exit(1)

print('Parsing data...')
data = req.json()['data'][0]

print('Validating data...')
if data['areaName'] != 'United Kingdom':
    print('Expected areaName: United Kingdom but got', data['areaName'])
    exit(1)
if data['date'] != date:
    print('Expected date: ' + date + ' but got', data['date'])
    exit(1)

print('Logging into Wikipedia...')
s = requests.Session()
req = s.get('https://en.wikipedia.org/w/api.php?action=query&meta=tokens&type=login&format=json')
req = s.post('https://en.wikipedia.org/w/api.php?action=login&format=json', {
    'lgname': os.environ.get('WIKIPEDIA_BOT_USERNAME'),
    'lgpassword': os.environ.get('WIKIPEDIA_BOT_PASSWORD'),
    'lgtoken': req.json()['query']['tokens']['logintoken']
})
if "login" not in req.json() or req.json()['login']['result'] != 'Success':
    print('Failed to login to Wikipedia:')
    print(req.text)
    exit(1)

print('Getting current page...')
req = s.get('https://en.wikipedia.org/w/index.php?title=User:DomdomeggBot/Template:COVID-19_pandemic_data&action=raw')
currentpage = req.text

# Check the existing data isn't too crazy, so we're probably in the right place and not breaking anything else
print('Validating existing data...')
casesmatch = re.search('^\\|([0-9,]+)<!--ANCHOR: UK CASES', currentpage, flags=re.MULTILINE)
if not casesmatch:
    print('Failed to find cases anchor in article, aborting...')
    exit(1)
casesspan = casesmatch.span(1)
currentpagecases = int(currentpage[casesspan[0]:casesspan[1]].replace(',', ''))
if currentpagecases > data['cases']:
    print('New cases figure is less than existing cumulative cases. Aborting...')
    exit(1)
if currentpagecases * 1.1 < data['cases']:
    print('New cases figure is >10% existing cumulative cases, which seems unlikely. Aborting...')
    exit(1)
deathsmatch = re.search('^\\|([0-9,]+)<!--ANCHOR: UK DEATHS', currentpage, flags=re.MULTILINE)
if not deathsmatch:
    print('Failed to find deaths anchor in article, aborting...')
    exit(1)
deathsspan = deathsmatch.span(1)
currentpagedeaths = int(currentpage[deathsspan[0]:deathsspan[1]].replace(',', ''))
if currentpagedeaths > data['deaths']:
    print('New deaths figure is less than existing cumulative deaths. Aborting...')
    exit(1)
if currentpagedeaths * 1.1 < data['deaths']:
    print('New deaths figure is >10% existing cumulative deaths, which seems unlikely. Aborting...')
    exit(1)

# Make edits
print('Calculating edits...')
newtext = currentpage[:casesspan[0]] + "{:,}".format(data['cases']) + currentpage[casesspan[1]:deathsspan[0]] + "{:,}".format(data['deaths']) + currentpage[deathsspan[1]:]
if newtext == currentpage:
    print('No edits to make')
    exit(0)

print('Making edits...')
req = s.get('https://en.wikipedia.org/w/api.php?action=query&format=json&meta=tokens')
req = s.post('https://en.wikipedia.org/w/api.php?action=edit&format=json&title=User:DomdomeggBot/Template:COVID-19_pandemic_data', {
    'text': newtext,
    'token': req.json()['query']['tokens']['csrftoken'],
    'bot': True,
    'summary': '[bot] United Kingdom'
})

if "edit" in req.json() and ['edit']['result'] == 'Success':
    print('Edit complete!')
else:
    print('Something went wrong making edits:')
    print(req.text)
    exit(1)
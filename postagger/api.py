from json import loads
from bson.objectid import ObjectId
from datetime import datetime
from random import randrange

from django.http import JsonResponse, HttpResponse
from users.models import User
from .models import Evaluation
from .rule import sanitize_tags
import environ
import redis

root = environ.Path(__file__) - 2 # three folder back (/a/b/c/ - 3 = /)
env = environ.Env(DEBUG=(bool, False),) # set default values and casting
environ.Env.read_env(root('djamongo/.env')) # reading .env file

def on_fetch (request, userid):
	response = {'unevaluated':None}
	
	# if there is session with such user id exists already
	if ('user_id' in request.session):
		# get user id
		this_user_id = request.session['user_id']
		if (request.user.is_authenticated()):
			this_user_id = User.objects.get(username=userid).id
		
		# search sentence that is not evaluated by this user yet
		search_criteria = {
			'$or': [{
				'verify_tag': {'$exists': False}
			}, {
				'$and': [
					{ 'verify_tag': {'$exists': True} }, 
					{ 'verify_tag.user_id': { 
						'$ne': this_user_id
					}},
					{'$where':'this.verify_tag.length<10'}
				]
			}]
		}
		
		unevaluated_sentences = Evaluation.objects.mongo_find(search_criteria)
		unevaluated_total = unevaluated_sentences.count()
		
		# if there are unevaluated
		if (unevaluated_total > 0):
			sentence = unevaluated_sentences[randrange(0, unevaluated_total)]
			sentence['_id'] = str(sentence['_id'])
			sanitize_tags(sentence['auto_tag'])
			response['unevaluated'] = sentence
			
	return JsonResponse(response)

def on_submit (request):
	response_code = 404
	if (request.method == 'POST'):
		response_code = 200
		
		evaluation_result = loads(request.body.decode('utf-8'))
		this_user_id = evaluation_result['user']
		if (request.user.is_authenticated()):
			this_user_id = request.session['user_number_id']
		
		Evaluation.objects.mongo_update({
			'_id': ObjectId(evaluation_result['oid'])
		}, 
		{
			'$push': {
				'verify_tag': {
					'user_id': this_user_id,
					'created_at': datetime.now().isoformat(),
					'tag': evaluation_result['eval']
				}
			}
		})
		
	return HttpResponse(status=response_code)	
	
def on_overview_requested (request):
	try:
		conn = redis.StrictRedis(
			host='127.0.0.1',
			port=6379,
			password='')
		conn.ping()
		print('Connected!')
	except Exception as ex:
		print('Error:', ex)
		exit('Failed to connect, terminating.')

	response = {
		"evaluated_total": float(conn.get('total_evaluated')),
		"accuracy_pos": float(conn.get('pos_accuracy')),
		"accuracy_iobes": float(conn.get('iobes_accuracy')),
		"accuracy_total": float(conn.get('overall_accuracy')),
		"model_name": str(env('MODEL_NAME')),
		"model_version": str(env('MODEL_VERSION'))
	}

	return JsonResponse(response)
	
def on_search_requested (request, searchkey, status, page):
	
	search_criteria = {
		'$and': [
			{'sentence': {'$exists': True}}
		]
	}

	if (searchkey != ''):
		search_criteria['$and'][0]['sentence'] = {
			'$regex': '.*' + searchkey.replace("%20", " ") + '.*', 
			'$options': 'i'
		}
	
	if (status in ('pending','completed')):
		search_criteria['$and'].append({'status': status})
	
	sentences_per_page = 10
	response = {
		'matched': list(),
		'max_page': 0,
	}
	
	all_matched = Evaluation.objects.mongo_find(search_criteria)
	response['max_page'] = (all_matched.count() // sentences_per_page) + 1
	sentences_searched = all_matched.skip((int(page) - 1) * sentences_per_page).limit(sentences_per_page)
	
	for sentence in sentences_searched:
		sentence['_id'] = str(sentence['_id'])
		response['matched'].append(sentence)
		auto_tagged = sentence['auto_tag']
		
		if 'verify_tag' not in sentence:
			continue
			
		reviews = sentence['verify_tag']
		
		# calculate accuracy for each word
		for t in range(0, len(auto_tagged)):
			right_tag = sum([1 for a in range(0, len(reviews)) if auto_tagged[t]['tags'] == reviews[a]['tag'][t]['tags']])
			auto_tagged[t]['accuracy'] = right_tag / len(reviews)
			
		del sentence['verify_tag']
		
	return JsonResponse(response)
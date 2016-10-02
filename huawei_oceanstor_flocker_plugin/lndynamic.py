# Copyright (c) 2015 LunaNode Hosting Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is furnished to do
# so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

class LNDynamic:
	LNDYNAMIC_URL = 'https://dynamic.lunanode.com/api/{CATEGORY}/{ACTION}/'

	def __init__(self, api_id, api_key):
		if len(api_id) != 16:
			raise InvalidArgumentException('Supplied api_id incorrect length, must be 16')
		if len(api_key) != 128:
			raise InvalidArgumentException('Supplied api_key incorrect length, must be 128')

		self.api_id = api_id
		self.api_key = api_key
		self.partial_api_key = api_key[:64]

	def request(self, category, action, params = {}):
		import json
		import time
		import hmac
		import hashlib
		import urllib
		import urllib2

		url = self.LNDYNAMIC_URL.replace('{CATEGORY}', category).replace('{ACTION}', action)
		request_array = dict(params)
		request_array['api_id'] = self.api_id
		request_array['api_partialkey'] = self.partial_api_key
		request_raw = json.dumps(request_array)
		nonce = str(int(time.time()))
		handler = "%s/%s/" % (category, action)
		hasher = hmac.new(self.api_key, '%s|%s|%s' % (handler, request_raw, nonce), hashlib.sha512)
		signature = hasher.hexdigest()

		data = urllib.urlencode({'req': request_raw, 'signature': signature, 'nonce': nonce})
		content = urllib2.urlopen(urllib2.Request(url, data)).read()

		try:
			response = json.loads(content)
		except ValueError:
			raise APIException('Server gave invalid response (could not decode).')

		if 'success' not in response:
			raise APIException('Server gave invalid repsonse (missing success key)')
		elif response['success'] != 'yes':
			if 'error' in response:
				raise APIException('API error: ' + response['error'])
			else:
				raise APIException('Unknown API error')

		return response

class InvalidArgumentException(Exception):
	pass

class APIException(Exception):
	pass
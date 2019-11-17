from flask import jsonify


class HTTPResponse(tuple):
	def __new__(cls, message='', status_code=200, status='ok', data=None, cookies={}):
		resp = jsonify({
			'status': status,
			'message': message,
			'data': data,
		})
		for c in cookies:
			if cookies[c] == None:
				resp.delete_cookie(c)
			else:
				resp.set_cookie(c, cookies[c])
		return super().__new__(tuple, (resp, status_code))


class HTTPError(HTTPResponse):
	def __new__(cls, message, status_code, data=None):
		return super().__new__(HTTPResponse, message, status_code, 'err', data)

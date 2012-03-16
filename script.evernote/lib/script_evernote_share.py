from xnote import EvernoteSession, getSetting, easypassword, parsePassword, getUserKey, ERROR, EvernoteSessionError, getUserList

import ShareSocial #@UnresolvedImport

def doShareSocial():
	return EvernoteTargetFunctions()

class EvernoteTargetFunctions(ShareSocial.TargetFunctions):
	def __init__(self):
		self.session = EvernoteSession()
		
	def getUserPass(self,user):
		password = getSetting('login_pass_%s' % user)
		if not password: return False
		method, keyfile, password = parsePassword(password)
		password = easypassword.decryptPassword(getUserKey(user),password,method=method,keyfile=keyfile)
		return user,password
	
	def startSession(self,user=None):
		if not user: user = getSetting('last_user')
		if not user: return
		if self.session.username == user: return
		user,password = self.getUserPass(user)
		if not user: return False
		self.session.setUserPass(user, password)
		self.session.startSession()
		self.session.getNotebooks()
		return True
	
	def changeUser(self,user=None):
		if not user: return
		if not self.startSession(user): return
			
	def cc(self,html):
		return html.replace('&','&amp;')
	
	def getUsers(self,share=None):
		ulist = []
		for user in getUserList():
			ulist.append({'id':user,'name':user})
		return ulist
	
	def share(self,share,user=None):
		try:
			self.startSession(user)
			session = self.session
			title = self.cc(share.title)
			self.setHTTPConnectionProgressCallback(share)
			if share.shareType == 'imagefile':
				session.createNote(title=title,image_files=[share.media],lat=share.getLatitude(),lon=share.getLongitude())
			elif share.shareType == 'image':
				session.createNote(html=self.cc(share.asHTML(True)),title=title,lat=share.getLatitude(),lon=share.getLongitude())
			elif share.shareType == 'video':
				session.createNote(html=self.cc(share.asHTML()),title=title,lat=share.getLatitude(),lon=share.getLongitude())
			elif share.shareType == 'text':
				session.createNote(text=self.cc(share.html),title=title,lat=share.getLatitude(),lon=share.getLongitude())
			elif share.shareType == 'html':
				session.createNote(html=self.cc(share.html),title=title,lat=share.getLatitude(),lon=share.getLongitude())
			else:
				return share.failed('Cannot share this type')
			return share.succeeded()
		except EvernoteSessionError, e:
			ERROR('Sharing failed: %s - %s' % (e.message,e.parameter))
			return share.failed(e.message)
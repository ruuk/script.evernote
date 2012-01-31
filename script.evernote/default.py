# -*- coding: utf-8 -*-
import xbmcaddon, xbmc, xbmcgui #@UnresolvedImport
import sys, os, re, traceback, glob, time

#Evernote Imports
import hashlib
import binascii
from xml.sax.saxutils import escape
import thrift.protocol.TBinaryProtocol as TBinaryProtocol
import thrift.transport.THttpClient as THttpClient
import evernote.edam.userstore.UserStore as UserStore
import evernote.edam.userstore.constants as UserStoreConstants
import evernote.edam.notestore.NoteStore as NoteStore
import evernote.edam.type.ttypes as Types
import evernote.edam.error.ttypes as Errors

__author__ = 'ruuk'
__url__ = 'http://code.google.com/p/evernote-xbmc/'
__date__ = '1-25-2012'
__version__ = '0.1.1'
__addon__ = xbmcaddon.Addon(id='script.evernote')
__lang__ = __addon__.getLocalizedString

ACTION_MOVE_LEFT      = 1
ACTION_MOVE_RIGHT     = 2
ACTION_MOVE_UP        = 3
ACTION_MOVE_DOWN      = 4
ACTION_PAGE_UP        = 5
ACTION_PAGE_DOWN      = 6
ACTION_SELECT_ITEM    = 7
ACTION_HIGHLIGHT_ITEM = 8
ACTION_PARENT_DIR_OLD = 9
ACTION_PARENT_DIR     = 92
ACTION_PREVIOUS_MENU  = 10
ACTION_SHOW_INFO      = 11
ACTION_PAUSE          = 12
ACTION_STOP           = 13
ACTION_NEXT_ITEM      = 14
ACTION_PREV_ITEM      = 15
ACTION_SHOW_GUI       = 18
ACTION_PLAYER_PLAY    = 79
ACTION_MOUSE_LEFT_CLICK = 100
ACTION_CONTEXT_MENU   = 117

THEME = 'Default'

import locale
loc = locale.getdefaultlocale()
print loc
ENCODING = loc[1] or 'utf-8'

def ENCODE(string):
	return string.encode(ENCODING,'replace')

def LOG(message):
	xbmc.log('X-NOTE: %s' % ENCODE(str(message)))
	
def ERROR(message):
	LOG(message)
	traceback.print_exc()
	err = str(sys.exc_info()[1])
	return err

class EvernoteSessionError(Exception):
	def __init__(self,func,meth,e):
		errorText = Errors.EDAMErrorCode._VALUES_TO_NAMES[e.errorCode]
		Exception.__init__(self, errorText)
		self.error = e
		self.code = e.errorCode
		self.function = func
		self.method = meth
		self.parameter = e.parameter
		self.message = errorText
			
class EvernoteSession():
	def __init__(self):
		self.consumerKey = "ruuk25-6163"
		self.consumerSecret = "20ff7fdf04db11ec"
		self.evernoteHost = "sandbox.evernote.com"
		self.userStoreUri = "https://" + self.evernoteHost + "/edam/user"
		self.noteStoreUriBase = "https://" + self.evernoteHost + "/edam/note/"
		
		self.userStoreHttpClient = THttpClient.THttpClient(self.userStoreUri)
		self.userStoreProtocol = TBinaryProtocol.TBinaryProtocol(self.userStoreHttpClient)
		self.userStore = UserStore.Client(self.userStoreProtocol)
		
	def processCommandLine(self):
		if len(sys.argv) < 3:
			print "Arguments:  <username> <password>";
			return None

		username = sys.argv[1]
		password = sys.argv[2]
		
		return username,password
		
	def setUserPass(self,user,password):
		self.user = user
		self.password = password
		
	def startSession(self,authResult=None):
		self.defaultNotebook = None
		self.notebooks = []
		
		versionOK = self.userStore.checkVersion("Python EDAMTest",
										   UserStoreConstants.EDAM_VERSION_MAJOR,
										   UserStoreConstants.EDAM_VERSION_MINOR)
		
		LOG("EDAM protocol version up to date? - %s " % str(versionOK))
		if not versionOK:
			return None
		
		# Authenticate the user
		if not authResult:
			authResult = self.authenticate(self.user, self.password)
		
		self.user = authResult.user
		self.authToken = authResult.authenticationToken
		LOG("Authentication was successful for %s" % self.user.username)
		LOG("Authentication token = %s" % self.authToken)
		
		noteStoreUri =  self.noteStoreUriBase + self.user.shardId
		noteStoreHttpClient = THttpClient.THttpClient(noteStoreUri)
		noteStoreProtocol = TBinaryProtocol.TBinaryProtocol(noteStoreHttpClient)
		self.noteStore = NoteStore.Client(noteStoreProtocol)
		
		return self.user

	def authenticate(self,user, password):
		try:
			return self.userStore.authenticate(user, password, self.consumerKey, self.consumerSecret)
		except Errors.EDAMUserException as e:
			# See http://www.evernote.com/about/developer/api/ref/UserStore.html#Fn_UserStore_authenticate
			parameter = e.parameter
			errorCode = e.errorCode
			errorText = Errors.EDAMErrorCode._VALUES_TO_NAMES[errorCode]
			
			LOG("Authentication failed (parameter: " + parameter + " errorCode: " + errorText + ")")
			
			if errorCode == Errors.EDAMErrorCode.INVALID_AUTH:
				if parameter == "consumerKey":
					LOG("Consumer key was not accepted by %s" % self.evernoteHost)
				elif parameter == "username":
					LOG("You must authenticate using a username and password from %s" % self.evernoteHost)
				elif parameter == "password":
					LOG("The password entered is incorrect")
			raise EvernoteSessionError('startSession()','userStore.authenticate',e)
		
	def getNotebooks(self,ignoreCache=False):
		if self.notebooks and not ignoreCache: return self.notebooks
		try:
			notebooks = self.noteStore.listNotebooks(self.authToken)
		except Errors.EDAMUserException as e:
			raise EvernoteSessionError('getNotebooks()','noteStore.listNotebooks',e)
		except Errors.EDAMSystemException as e:
			raise EvernoteSessionError('getNotebooks()','noteStore.listNotebooks',e)
		
		self.notebooks = notebooks
		LOG("Found %s notebooks:" % len(notebooks))
		for notebook in notebooks:
			LOG("  * %s" % notebook.name)
			if notebook.defaultNotebook:
				self.defaultNotebook = notebook
		return notebooks

	def getNotebookCounts(self):
		try:
			ncc = self.noteStore.findNoteCounts(self.authToken,NoteStore.NoteFilter(),False)
		except Errors.EDAMUserException as e:
			raise EvernoteSessionError('getNotebookCounts()','noteStore.findNoteCounts',e)
		except Errors.EDAMSystemException as e:
			raise EvernoteSessionError('getNotebookCounts()','noteStore.findNoteCounts',e)
		
		return ncc
		
	def getNotebookByGuid(self,guid):
		notebooks = self.getNotebooks()
		for nb in notebooks:
			if nb.guid == guid: return nb
		return None
	
	def getNotebookByName(self,notebook_name):
		notebooks = self.getNotebooks()
		for nb in notebooks:
			if nb.name == notebook_name: return nb
		return None
	
	def getNoteByGuid(self,guid):
		try:
			note = self.noteStore.getNote(self.authToken, guid, True, False, False, False)
		except Errors.EDAMUserException as e:
			raise EvernoteSessionError('getNoteByGuid()','noteStore.getNote',e)
		except Errors.EDAMSystemException as e:
			raise EvernoteSessionError('getNoteByGuid()','noteStore.getNote',e)
		return note
	
	def getNoteList(self,guid=None,notebook=None):
		if not guid:
			if not notebook: return
			guid = notebook.guid
		LOG('Getting notes for notebook - guid: %s' % guid)
		nf = NoteStore.NoteFilter()
		nf.notebookGuid = guid
		try:
			notes = self.noteStore.findNotes(self.authToken,nf,0,999)
		except Errors.EDAMUserException as e:
			raise EvernoteSessionError('getNoteList()','noteStore.findNotes',e)
		except Errors.EDAMSystemException as e:
			raise EvernoteSessionError('getNoteList()','noteStore.findNotes',e)
		return notes
		
	def prepareText(self,text):
		return re.sub('[\n\r]+','<br />',escape(text))
		
	def deleteNote(self,guid=None,note=None):
		if not guid: guid = note.guid
		try:
			self.noteStore.deleteNote(self.authToken, guid)
		except Errors.EDAMUserException as e:
			raise EvernoteSessionError('deleteNote()','noteStore.deleteNote',e)
		except Errors.EDAMSystemException as e:
			raise EvernoteSessionError('deleteNote()','noteStore.deleteNote',e)
		
		LOG("Successfully deleted note with guid: %s" % (guid))
		
	def createNote(self,text='',image_files=[],notebook=None,title=''):
		note = Types.Note()
		if not title:
			if text:
				title = text.splitlines()[0][:30]
		if not title:
			if image_files: title = os.path.basename(image_files[0])
		if not title: title = 'UNTITLED'
		
		if notebook and not notebook.defaultNotebook:
			LOG("Creating a new note (%s) in notebook: %s" % (title,notebook.name))
		else:
			LOG("Creating a new note (%s) in default notebook: %s" % (title,self.defaultNotebook.name))
			notebook = self.defaultNotebook
			
		note.title = title
		note.content = '<?xml version="1.0" encoding="UTF-8"?>'
		note.content += '<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">'
		note.content += '<en-note>%s<br/>' % self.prepareText(text)
		
		if image_files:
			resources = []
			for ifile in image_files:
				root,ext = os.path.splitext(ifile)
				if ext == '.jpg': ext = '.jpeg'
				ext = ext[1:]
				image = open(ifile, 'rb').read()
				md5 = hashlib.md5()
				md5.update(image)
				mhash = md5.digest()
				hashHex = binascii.hexlify(mhash)
			
				data = Types.Data()
				data.size = len(image)
				data.bodyHash = mhash
				data.body = image
			
				resource = Types.Resource()
				resource.mime = 'image/' + ext
				resource.data = data
				resources.append(resource)
				note.content += '<en-media type="image/png" hash="' + hashHex + '"/>'
				
			note.resources = resources
			
		note.content += '</en-note>'
		try:
			createdNote = self.noteStore.createNote(self.authToken, note)
		except Errors.EDAMUserException as e:
			raise EvernoteSessionError('createNote()','noteStore.createNote',e)
		except Errors.EDAMSystemException as e:
			raise EvernoteSessionError('createNote()','noteStore.createNote',e)
		
		LOG("Successfully created a new note with GUID: %s" % createdNote.guid)
		return createdNote
	
	def deleteNotebook(self,guid=None,notebook=None):
		if not guid: guid = notebook.guid
		try:
			self.noteStore.expungeNotebook(self.authToken, guid)
		except Errors.EDAMUserException as e:
			raise EvernoteSessionError('deleteNotebook()','noteStore.expungeNotebook',e)
		except Errors.EDAMSystemException as e:
			raise EvernoteSessionError('deleteNotebook()','noteStore.expungeNotebook',e)
		
		LOG("Successfully deleted notebook with guid: %s" % (guid))
		
	def createNotebook(self,name,default=False):
		notebook = Types.Notebook()
		notebook.name = name
		try:
			createdNotebook = self.noteStore.createNotebook(self.authToken, notebook)
		except Errors.EDAMUserException as e:
			raise EvernoteSessionError('createNotebook()','noteStore.createNotebook',e)
		except Errors.EDAMSystemException as e:
			raise EvernoteSessionError('createNotebook()','noteStore.createNotebook',e)
		
		LOG("Successfully created a new notebook with GUID: %s" % createdNotebook.guid)
		return createdNotebook
		
	def getResourceData(self,guid):
		try:
			return self.noteStore.getResourceData(self.authToken, guid)
		except Errors.EDAMUserException as e:
			raise EvernoteSessionError('getResourceData()','noteStore.getResourceData',e)
		except Errors.EDAMSystemException as e:
			raise EvernoteSessionError('getResourceData()','noteStore.getResourceData',e)

def doKeyboard(prompt,default='',hidden=False):
	keyboard = xbmc.Keyboard(default,prompt)
	keyboard.setHiddenInput(hidden)
	keyboard.doModal()
	if not keyboard.isConfirmed(): return None
	return keyboard.getText()

def obfuscate(text):
	return binascii.hexlify(text.encode('base64'))
	
def deObfuscate(coded):
	return binascii.unhexlify(coded).decode('base64')

class XNoteSession():
	def __init__(self,window=None):
		self.window = window
		self._pdialog = None
		
		self.CACHE_PATH = os.path.join(xbmc.translatePath(__addon__.getAddonInfo('profile')),'cache')
		if not os.path.exists(self.CACHE_PATH): os.makedirs(self.CACHE_PATH)
		
		try:
			self.esession = EvernoteSession()
			if not self.startSession():
				self.window.close()
				return
		except EvernoteSessionError as e:
			self.error(e,message=__lang__(30041))
			self.window.close()
			return
		except:
			self.error(message=__lang__(30041))
			self.window.close()
			return
			
		self.showNotebooks()
	
	def startSession(self,user=None):
		user,password = self.getUserPass(user)
		if not user: return False
		self.esession.setUserPass(user, password)
		self.esession.startSession()
		return True
		
	def error(self,error=None,message=''):
		if error:
			ERROR('ES API Error - %s:%s - Param: %s - %s' % (error.function,error.method,error.parameter,error.message))
			err = 'ES API: %s' % error.message
		else:
			err = ERROR(message)
		self.showError(message,err)
	
	def showError(self,l1,l2='',l3=''):
		xbmcgui.Dialog().ok(__lang__(30040),l1,l2,l3)
		
	def cleanCache(self):
		root = self.CACHE_PATH
		expiration = 2592000
		day = 86400
		now = time.time()
		for folder in glob.glob(root):
			LOG('Cleaning Cache: %s' % folder)
			for image in glob.glob(folder + '/*.*'):
				show = os.path.basename(image)
				# retrieves the stats for the current jpeg image file
				# the tuple element at index 8 is the last-modified-date
				stats = os.stat(image)
				lastAccessDate = stats[7]
				days_left = int(((lastAccessDate + expiration) - now) / day)
				LOG('File %s last accessed: %s - %s days left.' % (show, time.strftime("%m/%d/%y", time.localtime(lastAccessDate)),days_left))
				# check if image-last-accessed-date is outdated
				if now - lastAccessDate > expiration:
					try:
						LOG('Removing: %s' % show)
						#os.remove(image)
					except OSError:
						LOG('Could not remove: %s' % show)
						
	def getFocusedItem(self,list_id):
		lc = self.window.getControl(list_id)
		return lc.getSelectedItem()
	
	def startProgress(self,caption=__lang__(30030),text=''):
		self._pdialog = xbmcgui.DialogProgress()
		self._pdialog.create(caption)
		self._pdialog.update(0,text)
		
	def updateProgress(self,pct=0,line1='',line2='',line3='',total=0):
		if total: pct = int((pct*100.0)/total)
		self._pdialog.update(pct,line1,line2,line3)
		
	def endProgress(self):
		if not self._pdialog: return
		self._pdialog.close()
		self._pdialog = None
		
	def notebookSelected(self):
		item = self.getFocusedItem(120)
		guid = item.getProperty('guid')
		self.setNotebookTitleDisplay(item.getProperty('name'))
		self.showNotes(guid)
		
	def setNotebookTitleDisplay(self,name=''):
		self.window.getControl(130).setLabel(__lang__(3021) + '   [COLOR FF888888]' + name + '[/COLOR]')
		
	def noteSelected(self):
		item = self.getFocusedItem(125)
		guid = item.getProperty('guid')
		note = self.esession.getNoteByGuid(guid)
		self.viewNote(note)
	
	def getUserPass(self,user=None,force=False):
		if force:
			user = doKeyboard(__lang__(30061))
		if not user:
			if __addon__.getSetting('choose_user') == 'true':
				user = self.chooseUser()
		if not user:
			user = __addon__.getSetting('last_user')
		if not user:
			user = self.chooseUser(0)
		if not user:
			user = doKeyboard(__lang__(30061))
		if not __addon__.getSetting('save_passwords') == 'true':
			__addon__.setSetting('login_pass_%s' % user,'')
		password = __addon__.getSetting('login_pass_%s' % user)
		if password:
			password = deObfuscate(password)
		else:
			password = doKeyboard(__lang__(30062) % user,hidden=True)
		if not self.addUser(user,password): return None,None
		__addon__.setSetting('last_user',user)
		if __addon__.getSetting('save_passwords') == 'true':
			__addon__.setSetting('login_pass_%s' % user,obfuscate(password))
		return user,password
	
	def addUser(self,user,password):
		userlist = __addon__.getSetting('user_list').split('@,@')
		if user in userlist: return True
		try:
			self.esession.authenticate(user, password)
		except EvernoteSessionError as e:
			if e.code == Errors.EDAMErrorCode.INVALID_AUTH:
				self.error(e, __lang__(30042))
				return False
		except:
			self.error(message=__lang__(30042))
			return False
		if not self.usersCount(): userlist = []
		userlist.append(user)
		__addon__.setSetting('user_list','@,@'.join(userlist))
		return True
		
	def chooseUser(self,index=None):
		if not self.usersCount(): return None
		users = __addon__.getSetting('user_list').split('@,@')
		if index != None: return users[index]
		idx = xbmcgui.Dialog().select(__lang__(30019),users)
		if idx < 0:
			return None
		else:
			return users[idx]
		
	def createNewUser(self):
		user,password = self.getUserPass(force=True)
		if not user: return
		self.changeUser(user)
	
	def changeUser(self,user=None):
		if not user: user = self.chooseUser()
		if not user: return
		if not self.startSession(user): return
		__addon__.setSetting('last_user',user)
		self.clearNotes()
		self.showNotebooks()
		self.window.initFocus()
		
	def usersCount(self):
		ulist = __addon__.getSetting('user_list')
		if not ulist: return 0
		users = ulist.split('@,@')
		return len(users)
			
	def doContextMenu(self):
		options = [__lang__(30011),__lang__(30012),__lang__(30013),__lang__(30016),__lang__(30014),__lang__(30015)]
		optionIDs = ['xbmclog','screenshot','write','notebook','adduser','changeuser']

		if self.window.getFocusId() == 125:
			options.append(__lang__(30017))
			optionIDs.append('deletenote')
		elif self.window.getFocusId() == 120:
			options.append(__lang__(30018))
			optionIDs.append('deletenotebook')
			
		idx = xbmcgui.Dialog().select(__lang__(30010),options)
		if idx < 0:
			return
		else:
			option = optionIDs[idx]
		try:
			err_msg = __lang__(30046)
			if option == 'xbmclog':
				self.createXBMCLogNote()
			elif option == 'screenshot':
				self.createScreenshotNote()
			elif option == 'write':
				self.createWriteNote()
			elif option == 'notebook':
				err_msg = __lang__(30049)
				self.createNotebook()
			elif option == 'adduser':
				err_msg = __lang__(30047)
				self.createNewUser()
			elif option == 'changeuser':
				err_msg = __lang__(30048)
				self.changeUser()
			elif option == 'deletenote':
				err_msg = __lang__(30051)
				self.deleteNote()
			elif option == 'deletenotebook':
				err_msg = __lang__(30052)
				self.deleteNotebook()
		except EvernoteSessionError as e:
			self.error(e,message=err_msg)
		except:
			self.error(message=err_msg)
	
	def getXBMCLog(self):
		log_file = xbmc.translatePath('special://temp/xbmc.log')
		lf = open(log_file,'r')
		data = lf.read()
		lf.close()
		return data
	
	def createXBMCLogNote(self):
		self.esession.createNote(self.getXBMCLog(),title=__lang__(30063))
		
	def createScreenshotNote(self):
		fname = xbmcgui.Dialog().browse(1, __lang__(30022), 'files','.png|.jpg|.gif',True,False,xbmc.translatePath('special://screenshots/'))
		if not fname: return
		self.esession.createNote(title=__lang__(30060) % os.path.basename(fname),image_files=[fname])
	
	def createWriteNote(self):
		title = doKeyboard(__lang__(30020))
		text = doKeyboard(__lang__(30021))
		if not text: return
		self.esession.createNote(text,title=title)
		self.notebookSelected()
	
	def createNotebook(self):
		title = doKeyboard(__lang__(30023))
		if not title: return
		if self.esession.notebooks:
			for n in self.esession.notebooks:
				if n.name == title:
					self.showError(__lang__(30050))
					return
		self.esession.createNotebook(title)
		self.showNotebooks()
		
	def deleteNote(self):
		item = self.getFocusedItem(125)
		guid = item.getProperty('guid')
		title = item.getLabel()
		if xbmcgui.Dialog().yesno(__lang__(30024), __lang__(30025), title):
			self.esession.deleteNote(guid)
			self.showNotebooks()
			self.notebookSelected()
			
	def deleteNotebook(self):
		item = self.getFocusedItem(120)
		guid = item.getProperty('guid')
		title = item.getLabel()
		if xbmcgui.Dialog().yesno(__lang__(30024), __lang__(30025), title):
			self.esession.deleteNotebook(guid)
			self.showNotebooks()
			#TODO: Perhaps clear the note list, when this is working we can check to see if we can still access the notes
		
	def showNotebooks(self):
		self.startProgress(text=__lang__(30031))
		try:
			notebooks = self.esession.getNotebooks()
			ncc = self.esession.getNotebookCounts()
			items = []
			for nb in notebooks:
				count = ncc.notebookCounts.get(nb.guid)
				ct_disp = ''
				if count: ct_disp = ' (%s)' % count
				item = xbmcgui.ListItem()
				item.setThumbnailImage('')
				item.setLabel(nb.name + ct_disp)
				item.setProperty('guid',nb.guid)
				item.setProperty('name',nb.name)
				items.append(item)
			wlist = self.window.getControl(120)
			wlist.reset()
			wlist.addItems(items)
		except EvernoteSessionError as e:
			self.error(e,message=__lang__(30043))
		except:
			self.error(message=__lang__(30043))
		finally:
			self.endProgress()
		
	def clearNotes(self):
		self.setNotebookTitleDisplay()
		self.window.getControl(125).reset()
		
	def showNotes(self,nbguid=None):
		if not nbguid: return
		self.startProgress(text=__lang__(30032))
		try:
			noteList = self.esession.getNoteList(nbguid)
			items = []
			ct=0
			tot= len(noteList.notes)
			for note in noteList.notes: 
				path = ''
				self.updateProgress(ct,__lang__(30032),note.title,'',total=tot)
				if note.resources:
					#print 'test'
					#print note.resources
					for res in note.resources:
						#print res.mime
						if 'image/' in res.mime:
							self.updateProgress(ct,__lang__(30032),note.title,res.attributes.fileName or '',total=tot)
							ext = '.' + res.mime.split('/',1)[1]
							filename = note.guid + ext
							path = self.isCached(filename)
							if not path:
								data = self.esession.getResourceData(res.guid)
								path = self.cacheImage(filename,data)
				item = xbmcgui.ListItem()
				item.setThumbnailImage(path)
				item.setLabel(note.title)
				item.setProperty('guid',note.guid)
				items.append(item)
				ct+=1
			items.reverse()
			wlist = self.window.getControl(125)
			wlist.reset()
			wlist.addItems(items)
		except EvernoteSessionError as e:
			self.error(e,message=__lang__(30044))
		except:
			self.error(message=__lang__(30044))
		finally:
			self.endProgress()
		
	def cacheImage(self,filename,data):
		path = os.path.join(self.CACHE_PATH,filename)
		ifile = open(path,'wb')
		ifile.write(data)
		ifile.close()
		return path
		
	def isCached(self,filename):
		path = os.path.join(self.CACHE_PATH,filename)
		if os.path.exists(path):
			st = os.stat(path)
			mtime = st[8] #modification time
			#modify the file timestamp
			os.utime(path,(int(time.time()),mtime))
			return path
		return ''
	
	def viewNote(self,note):
		self.startProgress(text=__lang__(30033))
		try:
			contents = note.content
			contents = re.sub('<!DOCTYPE.*?>','',contents)
			contents = re.sub(r'<en-media[^>]*type="image/[^>]*hash="([^"]+)"[^>]*/>',r'<img src="\1" />',contents)
			contents = re.sub(r'<en-media[^>]*hash="([^"]+)"[^>]*type="image/[^>]*/>',r'<img src="\1" />',contents)
			noteFile = os.path.join(self.CACHE_PATH,'notecontents.html')
			nf = open(noteFile,'w')
			nf.write(contents)
			nf.close()
			if note.resources:
				ct=0
				tot=len(note.resources)
				self.updateProgress(0,__lang__(30034))
				for res in note.resources:
					if 'image' in res.mime:
						self.updateProgress(ct,__lang__(30034),res.attributes.fileName or '',total=tot)
						#ext = '.' + res.mime.split('/',1)[1]
						filename = binascii.hexlify(res.data.bodyHash)
						path = self.isCached(filename)
						if not path:
							data = self.esession.getResourceData(res.guid)
							path = self.cacheImage(filename,data)
					ct+=1		
			url = 'file://%s' % noteFile
		except EvernoteSessionError as e:
			self.error(e,message=__lang__(30045))
		except:
			self.error(message=__lang__(30045))
		finally:
			self.endProgress()
			
		from webviewer import webviewer #@UnresolvedImport
		url,html = webviewer.getWebResult(url) #@UnusedVariable
		
	
class BaseWindow(xbmcgui.WindowXML):
	def __init__( self, *args, **kwargs):
		xbmcgui.WindowXML.__init__( self, *args, **kwargs )
		
	def onFocus( self, controlId ):
		self.controlId = controlId
		
	def onAction(self,action):
		#if action == ACTION_PARENT_DIR or
		if action == ACTION_PREVIOUS_MENU:
			try:
				self.onClose()
			except:
				ERROR('BaseWindow - doClose() Error')
				
			self.close()
			return True
		else:
			return False
		
	def onClose(self):
		pass
		
class MainWindow(BaseWindow):
	def __init__( self, *args, **kwargs):
		self.session = None
		BaseWindow.__init__( self, *args, **kwargs )
		
	def onInit(self):
		if not self.session:
			self.session = XNoteSession(self)
			self.initFocus()
		
	def initFocus(self):
		self.setFocusId(120)
		
	def onClick( self, controlID ):
		if controlID == 120:
			self.session.notebookSelected()
		if controlID == 125:
			self.session.noteSelected()
			
	def onAction(self,action):
		if BaseWindow.onAction(self, action): return
		if action == ACTION_CONTEXT_MENU:
			self.session.doContextMenu()
			
	def onClose(self):
		self.session.cleanCache()

def openWindow(window_name,session=None,**kwargs):
	windowFile = 'script-evernote-%s.xml' % window_name
	w = MainWindow(windowFile , xbmc.translatePath(__addon__.getAddonInfo('path')), THEME,session=session)
	w.doModal()			
	del w
		
openWindow('main')
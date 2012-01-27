# -*- coding: utf-8 -*-
import xbmcaddon, xbmc, xbmcgui #@UnresolvedImport
import sys, os, re, traceback

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
	xbmc.log('EVERNOTE-XBMC: %s' % ENCODE(str(message)))
	
def ERROR(message):
	LOG(message)
	traceback.print_exc()
	err = str(sys.exc_info()[1])
	return err

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
		
		self.defaultNotebook = None
		self.notebooks = []
		
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
		
	def startSession(self):
		versionOK = self.userStore.checkVersion("Python EDAMTest",
										   UserStoreConstants.EDAM_VERSION_MAJOR,
										   UserStoreConstants.EDAM_VERSION_MINOR)
		
		LOG("EDAM protocol version up to date? - %s " % str(versionOK))
		if not versionOK:
			return None
		
		# Authenticate the user
		try :
			authResult = self.userStore.authenticate(self.user, self.password,
												self.consumerKey, self.consumerSecret)
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
			return None
		
		self.user = authResult.user
		self.authToken = authResult.authenticationToken
		LOG("Authentication was successful for %s" % self.user.username)
		LOG("Authentication token = %s" % self.authToken)
		
		noteStoreUri =  self.noteStoreUriBase + self.user.shardId
		noteStoreHttpClient = THttpClient.THttpClient(noteStoreUri)
		noteStoreProtocol = TBinaryProtocol.TBinaryProtocol(noteStoreHttpClient)
		self.noteStore = NoteStore.Client(noteStoreProtocol)
		
		return self.user

	def getNotebooks(self,ignoreCache=False):
		if self.notebooks and not ignoreCache: return self.notebooks
		notebooks = self.noteStore.listNotebooks(self.authToken)
		self.notebooks = notebooks
		LOG("Found %s notebooks:" % len(notebooks))
		for notebook in notebooks:
			LOG("  * %s" % notebook.name)
			if notebook.defaultNotebook:
				self.defaultNotebook = notebook
		return notebooks

	def getNotebookCounts(self):
		ncc = self.noteStore.findNoteCounts(self.authToken,NoteStore.NoteFilter(),False)
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
		note = self.noteStore.getNote(self.authToken, guid, True, False, False, False)
		return note
	
	def getNoteList(self,guid=None,notebook=None):
		if not guid:
			if not notebook: return
			guid = notebook.guid
		nf = NoteStore.NoteFilter()
		nf.notebookGuid = guid
		notes = self.noteStore.findNotes(self.authToken,nf,0,999)
		return notes
		
	def prepareText(self,text):
		return re.sub('[\n\r]+','<br />',escape(text))
		
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
		createdNote = self.noteStore.createNote(self.authToken, note)
		
		LOG("Successfully created a new note with GUID: %s" % createdNote.guid)
		
	def getResourceData(self,guid):
		return self.noteStore.getResourceData(self.authToken, guid)

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
		
		self.CACHE_PATH = os.path.join(xbmc.translatePath(__addon__.getAddonInfo('profile')),'cache')
		if not os.path.exists(self.CACHE_PATH): os.makedirs(self.CACHE_PATH)
		
		self.esession = EvernoteSession()
		user,password = self.getUserPass()
		self.esession.setUserPass(user, password)
		self.esession.startSession()
		#self.esession.getNotebooks()
		#nb = self.esession.getNotebookByName('Frog Notes')
		#self.esession.createNote('This is a third test note!', ['icon.png'],nb)
		self.showNotebooks()
	
	def getFocusedItem(self,list_id):
		lc = self.window.getControl(list_id)
		return lc.getSelectedItem()
	
	def notebookSelected(self):
		item = self.getFocusedItem(120)
		guid = item.getProperty('guid')
		self.window.getControl(130).setLabel(__lang__(3021) + '   [COLOR FF888888]' + item.getProperty('name') + '[/COLOR]')
		#nb = self.esession.getNotebookByGuid(guid)
		self.showNotes(guid)
		
	def noteSelected(self):
		item = self.getFocusedItem(125)
		guid = item.getProperty('guid')
		note = self.esession.getNoteByGuid(guid)
		self.viewNote(note)
	
	def getUserPass(self):
		user = __addon__.getSetting('login_user')
		if not user:
			user = doKeyboard('Enter Username')
			__addon__.setSetting('login_user',user)
		password = __addon__.getSetting('login_pass')
		if password:
			password = deObfuscate(password)
		else:
			password = doKeyboard('Enter Password')
			__addon__.setSetting('login_pass',obfuscate(password))
		return user,password
	
	def doContextMenu(self):
		options = [__lang__(30011),__lang__(30012),__lang__(30013)]
		optionIDs = ['xbmclog','screenshot','write']

		idx = xbmcgui.Dialog().select(__lang__(30010),options)
		if idx < 0:
			return
		else:
			option = optionIDs[idx]
			
		if option == 'xbmclog':
			self.createXBMCLogNote()
		elif option == 'screenshot':
			self.createScreenshotNote()
		elif option == 'write':
			self.createWriteNote()
	
	def getXBMCLog(self):
		log_file = xbmc.translatePath('special://temp/xbmc.log')
		lf = open(log_file,'r')
		data = lf.read()
		lf.close()
		return data
	
	def createXBMCLogNote(self):
		self.esession.createNote(self.getXBMCLog(),title='XBMC Log')
		
	def createScreenshotNote(self):
		fname = xbmcgui.Dialog().browse(1, __lang__(30022), 'files','.png|.jpg|.gif',True,False,xbmc.translatePath('special://screenshots/'))
		if not fname: return
		self.esession.createNote(title='XBMC Screenshot: %s' % os.path.basename(fname),image_files=[fname])
	
	def createWriteNote(self):
		title = doKeyboard(__lang__(30020))
		text = doKeyboard(__lang__(30021))
		if not text: return
		self.esession.createNote(text,title=title)
		self.notebookSelected()
	
	def showNotebooks(self):
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
		wlist.addItems(items)
		
	def showNotes(self,nbguid=None):
		if not nbguid: return
		noteList = self.esession.getNoteList(nbguid)
		items = []
		for note in noteList.notes: 
			path = ''
			if note.resources:
				#print 'test'
				#print note.resources
				for res in note.resources:
					#print res.mime
					if 'image/' in res.mime:
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
		items.reverse()
		wlist = self.window.getControl(125)
		wlist.addItems(items)
		
	def cacheImage(self,filename,data):
		path = os.path.join(self.CACHE_PATH,filename)
		ifile = open(path,'wb')
		ifile.write(data)
		ifile.close()
		return path
		
	def isCached(self,filename):
		path = os.path.join(self.CACHE_PATH,filename)
		if os.path.exists(path): return path
		return ''
	
	def viewNote(self,note):
		contents = note.content
		contents = re.sub('<!DOCTYPE.*?>','',contents)
		contents = re.sub(r'<en-media[^>]*type="image/[^>]*hash="([^"]+)"[^>]*/>',r'<img src="\1" />',contents)
		contents = re.sub(r'<en-media[^>]*hash="([^"]+)"[^>]*type="image/[^>]*/>',r'<img src="\1" />',contents)
		noteFile = os.path.join(self.CACHE_PATH,'notecontents.html')
		nf = open(noteFile,'w')
		nf.write(contents)
		nf.close()
		if note.resources:
			for res in note.resources:
				if 'image' in res.mime:
					#ext = '.' + res.mime.split('/',1)[1]
					filename = binascii.hexlify(res.data.bodyHash)
					path = self.isCached(filename)
					if not path:
						data = self.esession.getResourceData(res.guid)
						path = self.cacheImage(filename,data)
						
		url = 'file://%s' % noteFile
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
			self.close()
			return True
		else:
			return False
		
class MainWindow(BaseWindow):
	def __init__( self, *args, **kwargs):
		self.session = None
		BaseWindow.__init__( self, *args, **kwargs )
		
	def onInit(self):
		self.session = XNoteSession(self)
		
	def onClick( self, controlID ):
		if controlID == 120:
			self.session.notebookSelected()
		if controlID == 125:
			self.session.noteSelected()
			
	def onAction(self,action):
		if BaseWindow.onAction(self, action): return
		if action == ACTION_CONTEXT_MENU:
			self.session.doContextMenu()

def openWindow(window_name,session=None,**kwargs):
	windowFile = 'script-evernote-%s.xml' % window_name
	w = MainWindow(windowFile , xbmc.translatePath(__addon__.getAddonInfo('path')), THEME,session=session)
	w.doModal()			
	del w
		
if False:
	es = EvernoteSession()
	user,password = es.processCommandLine()
	es.setUserPass(user, password)
	es.startSession()
	es.getNotebooks()
	nb = es.getNotebookByName('Frog Notes')
	es.createNote('This is a third test note!', ['icon.png'],nb)
else:
	openWindow('main')
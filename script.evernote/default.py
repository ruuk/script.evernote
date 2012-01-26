# -*- coding: utf-8 -*-
import xbmcaddon, xbmc, xbmcgui #@UnresolvedImport
import sys, os, time, re, traceback
import htmlentitydefs

#Evernote Imports
import hashlib
import binascii
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
#TODO: RE-ENABLE
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
	#xbmc.log('TVRAGE-EPS: %s' % ENCODE(str(message)))
	print 'EVERNOTE-XBMC: %s' % ENCODE(str(message))
	
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

	def getNotebooks(self):
		notebooks = self.noteStore.listNotebooks(self.authToken)
		LOG("Found %s notebooks:" % len(notebooks))
		for notebook in notebooks:
			LOG("  * %s" % notebook.name)
			if notebook.defaultNotebook:
				self.defaultNotebook = notebook
		return notebooks

	def getNotebookByName(self,notebook_name):
		notebooks = self.getNotebooks()
		for nb in notebooks:
			if nb.name == notebook_name: return nb
		return None
	
	def createNote(self,text='',image_files=[],notebook=None):
		if notebook and not notebook.defaultNotebook:
			LOG("Creating a new note in notebook: %s" % notebook.name)
		else:
			LOG("Creating a new note in default notebook: %s" % self.defaultNotebook.name)
			notebook = self.defaultNotebook
		
		note = Types.Note()
		note.title = "Test note from EDAMTest.py"
		note.content = '<?xml version="1.0" encoding="UTF-8"?>'
		note.content += '<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">'
		note.content += '<en-note>%s<br/>' % text
		
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

def doKeyboard(prompt,default='',hidden=False):
	keyboard = xbmc.Keyboard(default,prompt)
	keyboard.setHiddenInput(hidden)
	keyboard.doModal()
	if not keyboard.isConfirmed(): return None
	return keyboard.getText()

class XNoteSession():
	def __init__(self):
		self.esession = EvernoteSession()
		user,password = self.getUserPass()
		self.esession.setUserPass(user, password)
		self.esession.startSession()
		#self.esession.getNotebooks()
		#nb = self.esession.getNotebookByName('Frog Notes')
		#self.esession.createNote('This is a third test note!', ['icon.png'],nb)
		self.showNotebooks()
	
	def menuItemSelected(self):
		pass
	
	def getUserPass(self):
		user = doKeyboard('Enter Username')
		password = doKeyboard('Enter Password')
		return user,password
	
	def showNotebooks(self):
		notebooks = self.esession.getNotebooks()
		items = []
		for nb in notebooks:
			item = xbmcgui.ListItem()
			item.setThumbnailImage('')
			item.setLabel(nb.name)
			items.append(item)
		wlist = self.window.getControl(120)
		wlist.addItems(items)
	
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
		if self.session: XNoteSession()
		
	def onClick( self, controlID ):
		if controlID == 120:
			self.session.menuItemSelected()

def openWindow(window_name,session=None,**kwargs):
	windowFile = 'script-evernote-%s.xml' % window_name
	w = MainWindow(windowFile , xbmc.translatePath(__addon__.getAddonInfo('path')), THEME)
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
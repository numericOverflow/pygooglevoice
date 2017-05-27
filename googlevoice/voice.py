from conf import config
from util import *
import settings
import base64

qpat = re.compile(r'\?')

#if settings.DEBUG:
#    import logging
#    logging.basicConfig()
#    log = logging.getLogger('PyGoogleVoice')
#    log.setLevel(logging.DEBUG)
#else:
#    log = None

logging.basicConfig()
log = logging.getLogger('PyGoogleVoice')
if getattr(settings, "LOGGING_LEVEL", None) and settings.LOGGING_LEVEL in ['CRITICAL','ERROR','WARNING','INFO','DEBUG']:
    print('set logging to logging.' + str(settings.LOGGING_LEVEL))
    log.setLevel(str(settings.LOGGING_LEVEL))
    log.disabled = False
else:
    print('Logging not enabled')
    log.setLevel(99)
    log.disabled = True
    

class Voice(object):
    """
    Main voice instance for interacting with the Google Voice service
    Handles login/logout and most of the baser HTTP methods
    """
    #It would be better to get this from the __init__.py file, but I can't figure out how, so 
    #as a hack/workaround, we will also store it here... :(
    __version__ = '0.60'
    
    def __init__(self):
        #import class this one is dependent upon
        from voice import Voice_URI_Response
        
        #Build the user agent string to include current class version number
        self._user_agent_string = 'PyGoogleVoice/' + str(self.__version__)
        
        #Build our cookie jar
        self._cookiejar = CookieJar()
        self._cookie_processor = HTTPCookieProcessor(self._cookiejar)
        install_opener(build_opener(self._cookie_processor))

        for name in settings.FEEDS:
            setattr(self, name, self.__get_xml_page(name))

        setattr(self, 'message', self.__get_xml_page('message'))
        
#        try:
#        if getattr(settings, "DEBUG", None):
#            log.disabled = False
#        except:
#            pass  #leave DEBUG logging disabled if we can't find setting to enable

    ######################
    # Some handy methods
    ######################
#    def special_OLDVERSION(self):
#        """
#        Returns special identifier for your session (if logged in)
#        """
#        
#        #TEMP DUMP inbox to file ##########################
#        log.debug('Inside special() - requesting settings.inbox page...')
#        self.__debugWriteHTMLPageToTempFile(urlopen(settings.INBOX).read())
#        #TEMP DUMP inbox to file ##########################
#        
#        if hasattr(self, '_special') and getattr(self, '_special'):
#            return self._special
#        try:
#            try:
#                regex = bytes("('_rnr_se':) '(.+)'", 'utf8')
#            except TypeError:
#                regex = bytes("('_rnr_se':) '(.+)'")
#        except NameError:
#            regex = r"('_rnr_se':) '(.+)'"
#        try:
#            sp = re.search(regex, urlopen(settings.INBOX).read()).group(2)
#        except AttributeError:
#            sp = None
#        self._special = sp
#        return sp
#    special = property(special)
#

    def special(self):
        """
        Returns special identifier for your session (if logged in)
        """

        #Return the existing _special if it has been set and is not None
        if hasattr(self, '_special') and getattr(self, '_special'):
            log.debug('special()=>_special already exists and is '+str(self._special))
            return self._special
        else:
            log.debug('special()=>_special not yet definded')
        try:
            try:
                regex = bytes('"rnr_xsrf_token"\s?:\s?"(.+?)"', 'utf8')
            except TypeError:
                regex = bytes('"rnr_xsrf_token"\s?:\s?"(.+?)"')
        except NameError:
            regex = r'"rnr_xsrf_token"\s?:\s?"(.+?)"'
        try:
            log.debug('special()=> Attempting to fetch special from google...')
            #@TODO: Make this abstracted so it can be stored in settings or file instead of hardcoded here...
            content = self.__do_page('LOGIN_GV_INIT', data='{"gvx":"' + str(self._gvx) + '"}', terms = {"m":"init","v":"13"}, payloadType='text/plain;charset=UTF-8').get_content()
            sp = re.search(regex, content).group(1)
        except AttributeError:
            sp = None
            log.debug('special()=> oops! AttributeError encountered')            
        self._special = sp
        log.debug('special()=> self._special='+str(self._special))
        return sp
    special = property(special)    
    
    
    
    #def login(self, email=None, passwd=None, MFAKey=None):
    def login(self, email=None, passwd=None, MFAKey=None):
        """
        Login to the service using your Google Voice account
        Credentials will be propmpted for if not given as args or in the ``~/.gvoice`` config file
        """
        if hasattr(self, '_special') and getattr(self, '_special'):
            return self

        if email is None:
            email = config.email
        if email is None:
            email = input('Email address: ')

        if passwd is None:
            passwd = config.password
        if passwd is None:
            from getpass import getpass
            passwd = getpass()

        log.debug('Making initial call to start login process...')
        content = self.__do_page('login').get_content()
        
        # holy hackjob
#        formParms['GALX'] = re.search(r"type=\"hidden\"[^>]+name=\"GALX\"[^>]+value=\"(.+)\"", content).group(1)
#        #result = self.__do_page('login', {'Email': email, 'Passwd': passwd, 'GALX': GALX})
#        formParms['gxf'] = re.search(r"type=\"hidden\"[^>]+name=\"gxf\"[^>]+value=\"(.+)\"", content).group(1)
        log.debug('Got login page, scraping some values we need to pass to subsequent pages...')
        
        #Find the form variables
        formParms = {'Email': email, 'Passwd': passwd, 'service':'grandcentral'}        
        formParms.update(self.__scrapeParmsFromHTML(content, ['GALX','gxf']))
        
        #Find the form submission page
        formParms.update(self.__scrapeFormActionPageFromHTML(content))
        
        log.debug('Posting email/password and some scraped fields to login page...')
        result = self.__do_page('login_post',{'Email': email, 'Passwd': passwd, 'GALX': formParms['GALX'], 'gxf': formParms['gxf']})
        #result = self.__do_page(formParms.get('form.action') or 'login_post',{'Email': email, 'Passwd': passwd, 'GALX': formParms['GALX'], 'gxf': formParms['gxf']})
        
        #log.debug('login().first_post_result={0}'.format(result.read()))
        
        try:
            #assert not hasattr(result, 'geturl')
            #assert result.geturl()
            
            if result.response_object.geturl().startswith(getattr(settings, "MFAAUTH")):
                log.debug('===2-Factor challenge detected===')
                log.debug('Google 2-factor is redirecting us to this URL: {0}'.format(result.response_object.geturl()))
                
                log.debug('Searching for parameters to send with 2-Factor auth')
                resultHTML = str(result.get_content())    
                
                #Find the form variables                
                parmsToFind = ['TL','gxf','continue','challengeId','challengeType']
                formParms.update(self.__scrapeParmsFromHTML(resultHTML, parmsToFind))
                #Find the form submission page
                formParms.update(self.__scrapeFormActionPageFromHTML(content))
                log.debug('login().2FactorChallenge.formParms={0}'.format(str(formParms)))
                content = self.__MFAAuth(formParms, MFAKey)
                #self.__debugWriteHTMLPageToTempFile(content)
        except (AssertionError, AttributeError), e:
            log.debug('login()=> result.geturl() did not exist')
            print(str(e))

        try:
            #Now that we've logged in, we need to make sure we have the "gvx" cookie, if not we need to get it by calling this page:
            #content = self.__do_page('LOGIN_GVX', headers={'Referer':'https://accounts.google.com/signin/challenge/sl/password'}, terms={'pli':'1'})   
            log.debug('Fetching page to grab the gvx cookie value')
            ###SOMETIMES_WORKS###content = self.__do_page('LOGIN_GVX', terms={'pli':'1'}).get_content() 
            ###DOES NOT WORK### content = self.__do_page('LOGIN_GV_INIT', terms={'pli':'1'}).get_content() 
            content = self.__do_page('LOGIN_GVX', terms={'pli':'1'}).get_content() 
            self._gvx = dict((cookie.name, cookie.value) for cookie in self._cookiejar if cookie.name == 'gvx').get('gvx')
            log.debug('self._gvx={0}'.format(self._gvx))
        except AttributeError:
            print(str(e))
            raise LoginError

        del email, passwd, parmsToFind, formParms

        try:
            assert self.special
        except (AssertionError, AttributeError), e:
            print(str(e))
            raise LoginError
            
        log.debug('Login process complete')
        return self
        
    def logout(self):
        """
        Logs out an instance and makes sure it does not still have a session
        """
        self.__do_page('logout')
        del self._special
        assert self.special == None
        log.debug('Logout completed OK')
        
        return self

    def call(self, outgoingNumber, forwardingNumber=None, phoneType=None, subscriberNumber=None):
        """
        Make a call to an ``outgoingNumber`` from your ``forwardingNumber`` (optional).
        If you pass in your ``forwardingNumber``, please also pass in the correct ``phoneType``
        """
        if forwardingNumber is None:
            forwardingNumber = config.forwardingNumber
        if phoneType is None:
            phoneType = config.phoneType

        self.__validate_special_page('call', {
            'outgoingNumber': outgoingNumber,
            'forwardingNumber': forwardingNumber,
            'subscriberNumber': subscriberNumber or 'undefined',
            'phoneType': phoneType,
            'remember': '1'
        })

    __call__ = call

    def cancel(self, outgoingNumber=None, forwardingNumber=None):
        """
        Cancels a call matching outgoing and forwarding numbers (if given).
        Will raise an error if no matching call is being placed
        """
        self.__validate_special_page('cancel', {
            'outgoingNumber': outgoingNumber or 'undefined',
            'forwardingNumber': forwardingNumber or 'undefined',
            'cancelType': 'C2C',
        })

    def phones(self):
        """
        Returns a list of ``Phone`` instances attached to your account.
        """
        return [Phone(self, data) for data in self.contacts['phones'].values()]
    phones = property(phones)

    def settings(self):
        """
        Dict of current Google Voice settings
        """
        return AttrDict(self.contacts['settings'])
    settings = property(settings)

    def send_sms(self, phoneNumber, text):
        """
        Send an SMS message to a given ``phoneNumber`` with the given ``text`` message
        """
        #self.__validate_special_page('sms', {'phoneNumber': phoneNumber, 'text': text})
        self.__do_api_call({'m':'sms', 'n': phoneNumber, 'txt': text})

    def search(self, query):
        """
        Search your Google Voice Account history for calls, voicemails, and sms
        Returns ``Folder`` instance containting matching messages
        """
        #return self.__get_xml_page('search', data='?q=%s' % quote(query))()
        return self.__get_xml_page('search', data='?q={0}'.format(quote(query)))()

    def archive(self, msg, archive=1):
        """
        Archive the specified message by removing it from the Inbox.
        """
        if isinstance(msg, Message):
            msg = msg.id
        assert is_sha1(msg), 'Message id not a SHA1 hash'
        self.__messages_post('archive', msg, archive=archive)

    def delete(self, msg, trash=1):
        """
        Moves this message to the Trash. Use ``message.delete(0)`` to move it out of the Trash.
        """
        if isinstance(msg, Message):
            msg = msg.id
        assert is_sha1(msg), 'Message id not a SHA1 hash'
        self.__messages_post('delete', msg, trash=trash)

    def download(self, msg, adir=None):
        """
        Download a voicemail or recorded call MP3 matching the given ``msg``
        which can either be a ``Message`` instance, or a SHA1 identifier.
        Saves files to ``adir`` (defaults to current directory).
        Message hashes can be found in ``self.voicemail().messages`` for example.
        Returns location of saved file.
        """
        from os import path, getcwd
        if isinstance(msg, Message):
            msg = msg.id
        assert is_sha1(msg), 'Message id not a SHA1 hash'
        if adir is None:
            adir = getcwd()
        try:
            response = self.__do_page('download', msg)
        except:
            raise DownloadError
        fn = path.join(adir, '{0}.mp3'.format(msg))
        with open(fn, 'wb') as fo:
            fo.write(response.read())
        return fn

    def contacts(self):
        """
        Partial data of your Google Account Contacts related to your Voice account.
        For a more comprehensive suite of APIs, check out http://code.google.com/apis/contacts/docs/1.0/developers_guide_python.html
        """
        if hasattr(self, '_contacts'):
            return self._contacts
        self._contacts = self.__get_xml_page('contacts')()
        return self._contacts
    contacts = property(contacts)

    ######################
    # Helper methods
    ######################
    #def __do_page(self, page, data=None, headers={}, terms={}):
    def __do_page(self, page, data=None, headers={}, terms={}, payloadType=None):
        """
        Loads a page out of the settings and pass it on to urllib Request
        """
        #lookup the associated page from settings, or use as-is if not found (assumes page variable passed is a valid URL if not found in settings)
        url = getattr(settings, page.upper(), None) or str(page)
        
        #page = page.upper()
        if not payloadType and (isinstance(data, dict) or isinstance(data, tuple)):
            log.debug("__do_page() - data looks like dict or tuple, so being URL encoded")
            data = urlencode(data)
        headers.update({'User-Agent': self._user_agent_string})
        if log:
            log.debug('__do_page()=>[page]={0} [data]={1} [terms]={2} [headers]={3}'.format(url, data or '',  terms or '', headers))
        if page in ('DOWNLOAD', 'XML_SEARCH'):
            return urlopen(Request(url + data, None, headers))
        
        if data:
            if not payloadType:
                headers.update({'Content-type': 'application/x-www-form-urlencoded;charset=utf-8'})
            else:
                headers.update({'Content-type': payloadType})

        pageuri = url
        if len(terms) > 0:
            m = qpat.match(page)
            if m:
                pageuri += '&'
            else:
                pageuri += '?'
            for i, k in enumerate(terms.keys()):
                #pageuri += k + '=' + terms[k]
                pageuri += k + '=' + quote(str(terms[k]))
                if i < len(terms) - 1   :
                    pageuri += '&'
        #content = urlopen(Request(pageuri, data, headers))
        #self.__debugWriteHTMLPageToTempFile(content)
        #return content
        try:
            log.debug("__do_page() final built pageuri={0}".format(pageuri))
            response = Voice_URI_Response(urlopen(Request(pageuri, data, headers)))         
        except HTTPError as e:
            response = Voice_URI_Response(None, raw_content='HTML ERROR: {0}\r\n{1}'.format(str(e.code),str(e.read())))

            self.__debugWriteHTMLPageToTempFile(response.get_content())
        return response            
            
    def __build_API_payload(self):
        return '{"gvx":"' + self._gvx + '"}'
        
    def __do_api_call(self, terms):      
        """
        Makes a call to the GVoice API passing given args and current API version
        """
        #make sure we send the API verison with this call
        terms.update({"v":"13"})
        
        return self.__do_page('API_BASE', data=self.__build_API_payload(), terms = terms, payloadType='text/plain;charset=UTF-8').get_content()
            
    def __validate_special_page(self, page, data={}, **kwargs):
        """
        Validates a given special page for an 'ok' response
        """
        data.update(kwargs)
        load_and_validate(self.__do_special_page(page, data))

    _Phone__validate_special_page = __validate_special_page

    def __do_special_page(self, page, data=None, headers={}, terms={}):
        """
        Add self.special to request data
        """
        assert self.special, 'You must login before using this page'
        if isinstance(data, tuple):
            data += ('_rnr_se', self.special)
        elif isinstance(data, dict):
            data.update({'_rnr_se': self.special})
        return self.__do_page(page, data, headers, terms)

    _Phone__do_special_page = __do_special_page

    def __get_xml_page(self, page, data=None, headers={}):
        """
        Return XMLParser instance generated from given page
        """
        #return XMLParser(self, page, lambda terms={}: self.__do_special_page('XML_%s' % page.upper(), data, headers, terms).read())
        return XMLParser(self, page, lambda terms={}: self.__do_special_page('XML_{0}'.format(page.upper()), data, headers, terms).read())

    def __messages_post(self, page, *msgs, **kwargs):
        """
        Performs message operations, eg deleting,staring,moving
        """
        data = kwargs.items()
        for msg in msgs:
            if isinstance(msg, Message):
                msg = msg.id
            assert is_sha1(msg), 'Message id not a SHA1 hash'
            data += (('messages', msg),)
        return self.__do_special_page(page, dict(data))

    _Message__messages_post = __messages_post

    def __scrapeParmsFromHTML(self, HTMLString ='', parmNames=[]):
        """
        Handles scraping form <input> values from an HTML page.
        Requires a (case sensetive) list of form field names to find on page
        """ 
        log.debug('Scraping form Parameters ({0}) from HTML content'.format(str(parmNames)))
        
        formParms = {}
        
        for p in parmNames:
            match = re.search(r'<input[^>]+name="' + str(p) + r'"[^>]+value\s?=\s?"([^"]+)"', HTMLString)
            if match is not None:
                formParms[p] = match.group(1)
                log.debug('FOUND form hidden value "{0}"'.format(p))
            else:
                log.debug('Could not locate form hidden value "{0}"'.format(p))     
        
        return formParms 

    def __scrapeFormActionPageFromHTML(self, HTMLString =''):
        """
        Handles scraping form <POST action="xxx"> values from an HTML page.
        """ 
        log.debug('Scraping form poast page from HTML content')
        
        match = re.search(r'<form[^>]+action\s?=\s?"([^"]+)"[^>]+id="gaia_loginform"', HTMLString)
        if match is not None:
            p = match.group(1)
            log.debug('FOUND form POST action value "{0}"'.format(p))
        else:
            log.debug('Could not locate form hidden value')     
        
        return {'form.action': p}         

    def __MFAAuth(self, formParms=[], MFAKey=None):
        """
        Attempts to provide challenge/response to the Multi-Factor Authentication login page by generating 
        a TOTP based on the MFAKey if defined in settings, otherwise will prompt user to enter MFA code manually
        """    
        log.debug('__MFAAuth() called')
        if MFAKey is None:
            MFAKey = config.MFAKey
        
        try_count = 1
        num_tries = 5
        seconds_between_tries = 10
        
        if MFAKey is None:
            log.debug('No MFAKey found, prompting user for MFA_Code ...')
            from getpass import getpass

            MFA_Code = getpass("Enter 2-Factor Authentication (MFA) Code: ")
            if len(MFA_Code) == 6:
                content = self.__submitMFACodeToGoogle(MFA_Code,formParms)
                #self.__debugWriteHTMLPageToTempFile(content)
            else:
                print('Incorrect number of digits in MFA Code entered.')
                content = ''
                
            while (getattr(settings, "MFAAUTHWRONG") in content or len(MFA_Code)<>6 ) and try_count <= num_tries:
                try_count += 1
                if try_count > num_tries:
                    print('Too many MFA failures, exiting...')
                    exit()
                    
                print('Invalid MFA code, please wait at least {0} seconds before re-entering (attempt {1} of {2})'.format(seconds_between_tries, try_count, num_tries))
                #import time
                time.sleep(seconds_between_tries)
                
                MFA_Code = getpass("Enter 2-Factor Authentication (MFA) Code: ")
                if len(MFA_Code) == 6:
                    content = self.__submitMFACodeToGoogle(MFA_Code,formParms)
                    #self.__debugWriteHTMLPageToTempFile(content)
                else:
                    print('Incorrect number of digits in MFA Code entered.')                
                    content = ''
        else:
            content = self.__submitMFACodeToGoogle(self.__generateTOTP(MFAKey),formParms)
            #self.__debugWriteHTMLPageToTempFile(content)

            while getattr(settings, "MFAAUTHWRONG") in content and try_count <= num_tries:
                try_count += 1
                if try_count > num_tries:
                    print('Too many MFA failures, exiting...')
                    exit()
                    
                print('Invalid TOTP code, retrying after {0} seconds (attempt {1} of {2})'.format(seconds_between_tries, try_count, num_tries))
                #import time
                time.sleep(seconds_between_tries)
                
                content = self.__submitMFACodeToGoogle(self.__generateTOTP(MFAKey),formParms)
                #self.__debugWriteHTMLPageToTempFile(content)
                
        del MFAKey

        return content

    def __generateTOTP(self, MFAKey):
        """
        Generates and return TOTP from the MFA Key using either 1) pyotp python package or 2) external "oathtool" binary
        You really should install the pyotp python package if you want to use MFA, it is much easier as python-only solution.
        """      
    
        try:
            #Try using pyotp python package to generate TOTP
            from pyotp import TOTP
            log.debug('Generating TOTP 2-Factor (MFA) code using "pyotp" package')
            TOTP = TOTP(MFAKey).now()
            
        except ImportError, e:
            log.warning('**ERROR** "pyotp" python package, not found.  Please install so we can gederate TOTP MFA codes.  It can be installed with the command "pip install pyotp"')
            log.warning('Attempting to generate TOTP another way')
            
            try:
                #Otherwise try using oathtool binary to generate TOTP
                from subprocess import Popen
                from subprocess import PIPE as subprocess_PIPE

                log.debug('MFAKey found, converting to base32 so we can generate a TOTP')
                MFAKey = base64.b32decode(re.sub(r' ', '', MFAKey), casefold=True).encode("hex")
                log.debug('Generating TOTP 2-Factor (MFA) code using "oathtool" binary')

                p = Popen(['oathtool', '--totp', MFAKey], stdout=subprocess_PIPE, stderr=subprocess_PIPE)
                stdout, stderr = p.communicate()
                TOTP = re.search(r'([0-9]{6})', str(stdout)).groups()[0]
            except ImportError, e:
                log.critical('**ERROR** Generating TOTP 2-Factor (MFA) code using "oathtool" binary!')
                log.critical('Generating TOTP 2-Factor (MFA) code using "oathtool" binary')
                log.critical('**ERROR** - Unable to generate a TOTP.  You have 2 options:')
                log.critical('1) Install "pyotp" python package. It can be installed with the command "pip install pyotp"')
                log.critical('2) Install the "oathtool" binary executable from the "OATH Toolkit" place it somewhere in your system path. It can be found at "www.nongnu.org/oath-toolkit/"')
                exit(99)
        
        return TOTP
        
    def __submitMFACodeToGoogle(self, MFA_Code,formParms=[],):
        """
        Handles submitting MFA code & form paramters to google
        """ 
        log.debug('Submitting MFA Code ({0}) to Google'.format(MFA_Code))
        return self.__do_page('mfaauth_post', {'TL': formParms['TL'], 'service':formParms['service'], 'Pin':MFA_Code, 'pstMsg':'1',
                                         'challengeId': formParms['challengeId'], 'challengeType': formParms['challengeType'],
                                         'gxf': formParms['gxf'], 'continue': formParms['continue'], 'TrustedDevice':'on' }).read()
                                         
    def __debugWriteHTMLPageToTempFile(self, content):
        """
        Writes the content of an HTML page for easier debugging if something goes wrong
        """    
        if log.getEffectiveLevel() > 0:
            try:
                if getattr(settings, "SAVEPAGESTOFILE", None):
                    from tempfile import NamedTemporaryFile
                    # Clean up a NamedTemporaryFile on your own
                    # delete=True means the file will be deleted on close
                    #tmp = tempfile.NamedTemporaryFile(delete=False)
                    tmp = NamedTemporaryFile(delete=False)
                    try:
                        tmp.write(str(content))
                    except:
                        log.debug('Error writing content to file')

                    tmp.close()
                    log.debug('Saved HTML file to: "{0}"'.format(tmp.name))
            except:
                log.debug('Enable "SAVEPAGESTOFILE=True" in settings if you want to save intermediate pages to temp files')
                

class Voice_URI_Response(object):
    """
    Object to hold responses from web URL calls to google because the urllib.read() is one-time-only
    This object lets us keep the response content so we can access again, and still get at the urlopen results too
    """
    def __init__(self, response_object, raw_content=None):
        self.__response_object = response_object
        
        if response_object:
            self.__response_content = response_object.read()
        else:
            self.__response_content = raw_content
        
    def get_content(self):
        return self.__response_content
    content = property(get_content)
    
    def read(self):
        return self.get_content()    
    
    def get_response_object(self):
        return self.__response_object
    response_object = property(get_response_object)    
    


import os
import httplib2
import urllib2
import unicodedata
import re, urlparse
import xml.dom.minidom
import json               # FB API ritornano json data   
import requests           # request URLs FB

from apiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials

from datetime import date, time, datetime, timedelta
from dateutil.parser import parse

from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.template import Context

from alan.analytics.models import DailyMostViewed, TrendPageviews, DailyStatisticsSite
from alan.api.utils import *
from alan.utils import email

from httplib2 import Http

from alan.utils.log import print_log_message, print_log_exception

env = "PROD" # Nota bene impostare a "PROD" per produzione, "LOCAL" per locale
log_level = 'NORMAL' # Values "NONE" "NORMAL" "ALL"
only_send_mail = False

class EmailStatisticSite(object):
        def __init__(self, site_code, pageviews, users, pageviews_per_user, avarange_session_time, facebook, articles, trend_prev, trend_this, trend_sign, trend_incrase, day, month_name, year ):
            self.site_code = site_code
            self.pageviews = pageviews
            self.users = users
            self.pageviews_per_user = pageviews_per_user
            self.avarange_session_time = avarange_session_time
            self.facebook = facebook
            self.articles = articles
            self.trend_prev = trend_prev
            self.trend_this = trend_this
            self.trend_sign = trend_sign
            self.trend_incrase = trend_incrase
            self.day = day
            self.month_name = month_name
            self.year = year

class Command(BaseCommand):
    help = "Manutenzione analytics."    

    option_list = BaseCommand.option_list + (
        make_option(
            "-d",
            "--date",
            action = "store",
            type = "string",
            dest = "ref_date",
            default = None,
            help = "Opera sul giorno YYYYMMDD anziche' da oggi in avanti.",
            metavar="YYYYMMDD",
        ),          
    )
        
    def handle(self, *args, **options):
        
        # Interpreta il parametro --date. Se assente default Ieri
        if options['ref_date']:
            dt = datetime.strptime(options['ref_date'], "%Y%m%d")            
            date_to_scan = dt.date()            
        else:
            date_to_scan = date.today() - timedelta(1)                
        # Il giorno prima del giorno da scansionare. Default altro ieri
        day_before_date_to_scan = date_to_scan - timedelta(1)   
        # Avvia la generazione.        
        if(log_level=="ALL"):
            print "Dal giorno "+str(day_before_date_to_scan.strftime("%d-%m-%Y"))+" al giorno "+ str(date_to_scan.strftime("%d-%m-%Y"))    
        # Definire  auth scopes per request.
        scope = 'https://www.googleapis.com/auth/analytics.readonly'
        key_file_location = 'uplifted-aaaa.json'        
        # Autentificazione e costruzione del service.
        try:
            service = self.get_service(
                    api_name='analytics',
                    api_version='v3',
                    scopes=[scope],
                    key_file_location=key_file_location)
            sites = ["a", "b", "c"]            
            try:
                date_from_this_year = datetime(2019,1,1)   
                date_from_prev_year = datetime(2018,1,1)   
                date_to = date_to_scan            
                date_to_prev_year = date_to.replace(year=date_to.year-1)
            except Exception, e:
                print e                               
            if(log_level=="ALL" or log_level=="NORMAL"):
                print '--------------'
            if( not only_send_mail):
                for i in range(len(sites)):                
                    ''' GA'''                    
                    profile_id = self.get_profile_id(service, sites[i], True)                                        
                    # Salvo gli articoli piu letti il giorno prima di ieri o il giorno in input
                    self.save_results_daily_most_viewed(self.get_most_viewed_articles(service, profile_id, day_before_date_to_scan), sites[i], day_before_date_to_scan) 
                    # Salvo gli articoli piu letti ieri o il giorno in input                
                    self.save_results_daily_most_viewed(self.get_most_viewed_articles(service, profile_id, date_to_scan), sites[i], date_to_scan) 
                                       
                    # salvo info totali per ieri: visualizzazioni di pagina totali, gli utenti totali ecc                
                    resultStat = self.get_analytics_daily_statistics(service, profile_id, date_to_scan)                        
                    self.save_analytics_daily_statistics(resultStat.get('totalsForAllResults'), sites[i], date_to_scan)                                                                                             
                    
                    # Salvo Visualizzazioni di pagina da 1 gennaio 2019 a ieri                                    
                    pageviews_this_year = self.get_trend(service, profile_id, date_from_this_year, date_to)                                                                                                                                        
                    self.save_trend(pageviews_this_year.get('totalsForAllResults').get('ga:pageviews').encode("utf-8"), sites[i], date_from_this_year, date_to)                                                                
                    
                    # Salvo Visualizzazioni di pagina da 1 gennaio 2018 a ieri  WWW
                    pageviews_prev_year_www = self.get_trend(service, profile_id, date_from_prev_year, date_to_prev_year)                                                                                
                    # Salvo Visualizzazioni di pagina da 1 gennaio 2018 a ieri  MOBILE
                    # NB per i periodi pre novembre 2018 bisogna interrogare sia l'account mobile che www e sommare il dato                
                    profile_id_mob = self.get_profile_id(service, sites[i], False)                 
                    pageviews_prev_year_mob = self.get_trend(service, profile_id_mob, date_from_prev_year, date_to_prev_year)                                                                                
                    try:
                        pageviews_prev_year = str(int(pageviews_prev_year_www.get('totalsForAllResults').get('ga:pageviews')) + int(pageviews_prev_year_mob.get('totalsForAllResults').get('ga:pageviews')))
                    except Exception, e:
                        print e
                    self.save_trend(pageviews_prev_year, sites[i], date_from_prev_year, date_to_prev_year)   
                    ''' end GA    '''
                    ''' FB        '''
                    # Parameters in settings_all.py            
                    # Concatenate parameters to build first URL
                    fb_url = self.get_FB_url(sites[i])
                    if (fb_url is not None):                                        
                        # Ottengo i dati da FB
                        page_post_engagement = self.get_FB_data(fb_url)
                        # Salvo a DB i dati da FB
                        self.save_FB_data(sites[i], page_post_engagement, date_to_scan)                                                  
                    ''' end FB   '''
            # Invio email report giornaliero
            # TODO da verificare
            self.send_report_email(sites, date_from_prev_year, date_to_prev_year, date_from_this_year, date_to)
        except Exception, e:
            print("Errore in Autentificazione e costruzione del service.")
            print e           
     
    def get_FB_url(self, site):
        url = None
        try:    
            page_id      = settings.FACEBOOK_PAGE_ID_A
            access_token = settings.FACEBOOK_ACCESS_TOKEN_A
            if  site == 'a':
                page_id = settings.FACEBOOK_PAGE_ID_A
                access_token = settings.FACEBOOK_ACCESS_TOKEN_A
            elif site == 'b':
                page_id = settings.FACEBOOK_PAGE_ID_B
                access_token = settings.FACEBOOK_ACCESS_TOKEN_B
            elif site == 'c':
                page_id = settings.FACEBOOK_PAGE_ID_C
                access_token = settings.FACEBOOK_ACCESS_TOKEN_C
            url = settings.FACEBOOK_BASE_URL + page_id + settings.FACEBOOK_URL_PARAMETERS + '?access_token=' + access_token  + '&until=' + str(datetime.now()) + '&since=' + str(datetime.now() - timedelta(1))             
        except Exception, e:
            print 'Eccezione costruendo URL analytics di Facebook.'
            print e 
        return url
        
    def get_FB_data(self, first_url): 
        # vengono tornati solo un max di n, da capire, risultati e poi un link nel campo next da seguire. Nel caso specifico non serve perché ci basta un risultato.
        page_post_engagement = 0
        try:                                
            datas = json.loads(self.request_properly(first_url))                                                
            page_post_engagement = datas.get('data')[0].get('values')[0].get('value')                       
        except Exception, e:
            print 'Eccezione interrogando analytics di Facebook.'
            print e     
        return page_post_engagement

    def save_FB_data(self, site_code, page_post_engagement, date_to_scan):
        try: 
            site = get_site(site_code)        
            p = DailyStatisticsSite.objects.get(site = site, date= date_to_scan)                                    
            p.facebook_page_post_engagement = page_post_engagement
            p.save() 
            if(log_level=="ALL" or log_level=="NORMAL"):
                print 'Salvo statistiche giornaliere Facebook sito: '+site_code+' giorno:'+ str(date_to_scan.strftime("%d-%m-%Y")) +' page impression:'+ str(page_post_engagement)
        except Exception, e:
            print 'Eccezione salvando dati a DB analytics di Facebook.'
            print e     
        
    def request_properly(self, url):
              
        Success = False 
        # Systematic query
        while Success is False : 
            try :
                # Create an object containing our data
                if (env == 'PROD'):
                    # Per PROD con proxy:
                    proxies = {
                      'http': '',
                      'https': '',
                    }
                    requests.get(url, proxies=proxies)
                if (env  == 'LOCAL'):              
                    # Locale
                     request = requests.get(url)                
                # Standard response codes given by web site servers on the 
                # internet. The codes help identify the cause of the problem when     
                # a web page or other resource does not load properly. 
                status_code = request.status_code
                # 200: successful query
                if status_code == 200:
                    raw_data = request.text
                    Success = True
                # 4XX: Client error
                elif status_code == 400:                    
                    print(status_code, '\nRefresh your access TOKEN\n')
                    Success = True
                # Wait 5secs and retry
            except Exception as e:
                print (e, ' ', datetime.now())
                #print (e, '\n\t Please wait, Retrying...', datetime.now())
                #sleep(5)
        # Return data, we clean later		
        return raw_data
      
    def getMothName(self, number):
        m = {
        1 : 'Gennaio',
        2 : 'Febbraio',
        3 : 'Marzo',
        4 : 'Aprile',
        5 : 'Maggio',
        6 : 'Giugno',
        7 : 'Luglio',
        8 : 'Agosto',
        9 : 'Settembre',
        10 : 'Ottobre',
        11 : 'Novembre',
        12 : 'Dicembre'
        } 
        try:
            out = m[number]
            return out
        except:
            raise ValueError('Not a month')
    
    # Invia la mail con le statistiche
    def send_report_email(self, sites,  date_from_prev_year, date_to_prev_year, date_from_this_year, date_to):
        # Arrays utilizzati
        list_email_statistics_obj = []
        daily_most_viewed_objects = []            
        # Ciclo i siti e costruisco un unico Context
        for i in range(len(sites)):    
            try:            
                site = get_site(sites[i])  
                daily_stat = DailyStatisticsSite.objects.filter(site = site, date= date_to)
                daily_most_viewed_objects = []                        
                date_to_prev_year = date_to.replace(year=date_to.year-1)
                trend_prev_year = TrendPageviews.objects.filter(site = site, from_date = date_from_prev_year, to_date = date_to_prev_year)
                trendt_this_year = TrendPageviews.objects.filter(site = site, from_date = date_from_this_year, to_date = date_to)            
                
                for x in range(1, 10):                
                    dailyMostViewed = DailyMostViewed.objects.filter(site = site, views_date= date_to, position = x)                                
                    daily_most_viewed_objects.append(dailyMostViewed[0])        
                        
            except Exception, e:
                print 'Errore costruzione oggetti per email'
                print e          
            trend_incrase =  '%.2f'%( (trendt_this_year[0].pageviews - trend_prev_year[0].pageviews) / trend_prev_year[0].pageviews *100)
            if((trendt_this_year[0].pageviews - trend_prev_year[0].pageviews) > 0):
                trend_sign = '+'
            else:
                trend_sign = '-'            
            list_email_statistics_obj.append( EmailStatisticSite(
                                    sites[i], daily_stat[0].pageviews, daily_stat[0].users,
                                    daily_stat[0].pageviewsPerUser, daily_stat[0].avarangeSessionTime, daily_stat[0].facebook_page_post_engagement,
                                    daily_most_viewed_objects, trend_prev_year[0].pageviews,
                                    trendt_this_year[0].pageviews, trend_sign,trend_incrase,
                                    date_to.day ,self.getMothName(date_to.month), date_to.year)        
                                    )

        try:                        
            context = Context({                
                'list_email_statistics_obj': list_email_statistics_obj
            })            
        except Exception, e:
            print 'Errore costruzione context per email'            
            print e 

        # Invio email unica
        subject = 'Report analytics siti web - ' + str(date_to.day) +" "+ str(self.getMothName(date_to.month)) +" "+ str(date_to.year)
        template_email = 'email/analytics/mail_aggregate'
        to_addresses = ['xx@xxx.com']
        from_address = 'xxx@yy.com'        
        try:
            email.send_email(subject, context, template_email, to_addresses, from_address)  
            if(log_level=="NORMAL"):
                print ("Email Report giorno: "+ str(date_to.strftime("%d-%m-%Y")) +"  inviate a: "+";".join(to_addresses))                                       
        except Exception, e:
            print 'Errore invio email report giornaliero'
            print e                  
        return True
    
    # Ritorna il servizio per comunicare con le API Google Analytics
    def get_service(self, api_name, api_version, scopes, key_file_location):
        """
        Args:
            api_name: Il nome delle api a cui connettersi. Potrebbe essere altro Google oltre analytics
            api_version: Versione API.
            scopes: Lista auth scopes per autorizzare applicazione.
            key_file_location: path di un valido JSON avente le informazioni per chiave per connettersi. 

        Returns:
            Servizio connesso alla specifica API.
        """
        
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            os.path.join(os.path.dirname(__file__), './uplifted-aaaa.json'),            
            scopes=scopes
        )
        if (env == 'PROD'):
            # Per PROD con proxy:
            http_auth = credentials.authorize(Http(proxy_info = httplib2.ProxyInfo(httplib2.socks.PROXY_TYPE_HTTP_NO_TUNNEL, 'proxyserver', 1111, proxy_user = '', proxy_pass = '') ))
            # Costruzione dell'oggetto service.            
            # PROD
            service = build(api_name, api_version, http=http_auth) #credentials=credentials)
        if (env  == 'LOCAL'):              
            # Locale
            service = build(api_name, api_version, credentials=credentials)

        return service
        
    # Ritorna il ID profilo legato al account GA
    def get_profile_id(self, service, selectedSite, isWww):        
        # Get lista tutti gli accounts Google Analytics per questo user.
        accounts = service.management().accounts().list().execute()   
        try:        
            if accounts.get('items'):
                # Prendo il primo account Google Analytics.   TODO da capire se soluzione robusta                
                account = accounts.get('items')[0].get('id')
                # Lista tutte le properties per l'account.
                properties = service.management().webproperties().list(
                        accountId=account).execute()                  
                if properties.get('items'):
                    # Property-id basato sui parametri di input.                
                    selectedPropertyId = self.get_id_selected_site(selectedSite, isWww)                
                    for j in range(len(properties.get('items'))):                
                        property = properties.get('items')[j].get('id')                    
                        if property == selectedPropertyId: 
                            break                                                        

                    # Lista di tutte le views (profili) per la prima property.
                    profiles = service.management().profiles().list(
                            accountId=account,
                            webPropertyId=property).execute()                
                    if profiles.get('items'):
                        # Ritorno il primo view (profile) ID.  Es 9957885.                             
                        return profiles.get('items')[0].get('id')
        except Exception, e:
            print("Errore in get_profile_id di GA.")
        return None
        
    # Statistiche generiche GA sul sito per la data in input
    def get_analytics_daily_statistics(self, service, profile_id, date):       
        return service.data().ga().get(
                    ids='ga:' + profile_id,
                    start_date=date.strftime("%Y-%m-%d"), 
                    end_date=date.strftime("%Y-%m-%d"), 
                    metrics='ga:pageviews, ga:users, ga:avgSessionDuration',  
                    dimensions='ga:pagepath',
                    filters= 'ga:pagepath!~/xxxx/;ga:pagepath!~/yyyy/;ga:pagepath!~/zzzzz/'
                    ).execute()
        
    # Call API GA trend
    def get_trend(self, service, profile_id, date_from, date_to):    
        try:
            return service.data().ga().get(
                ids='ga:' + profile_id,
                start_date=date_from.strftime("%Y-%m-%d"), 
                end_date=date_to.strftime("%Y-%m-%d"), 
                metrics='ga:pageviews, ga:users, ga:avgSessionDuration',      
                dimensions='ga:pagepath',
                filters= 'ga:pagepath!~/xxxx/;ga:pagepath!~/yyyy/;ga:pagepath!~/zzzzz/'
                #max_results='2'
                ).execute()
        except Exception, e:
                print e       
    
    # Call API GA  articoli piu letti
    def get_most_viewed_articles(self, service, profile_id, date):         
        return service.data().ga().get(
                ids='ga:' + profile_id,
                start_date=date.strftime("%Y-%m-%d"), 
                end_date=date.strftime("%Y-%m-%d"), 
                metrics='ga:pageviews, ga:users',
                dimensions='ga:pageTitle, ga:pagepath',
                sort='-ga:pageviews',
                filters='ga:dimension2==ARTICLE', #custom filter article
                max_results='10'
                ).execute()
    
    # Salva a DB nella tabella statistiche
    def save_analytics_daily_statistics(self, results, site_code, date_to_scan):    
        if results:  
            try:                    
                pageviews = results.get('ga:pageviews') #.get('rows')[i][0]
                users = results.get('ga:users') #.get('rows')[i][1]
                pageviewsPerUser = float(pageviews)/float(users)
                rowData = int(float(results.get('ga:avgSessionDuration')))                                       #get('rows')[i][2]
                minutes = rowData//60                    
                seconds = rowData - (60 * minutes)                                        
                site = get_site(site_code)                
                # Pulisco i dati presenti a DB                
                DailyStatisticsSite.objects.filter(site = site, date= date_to_scan).delete()  
                if(log_level=="ALL" or log_level=="NORMAL"):
                    print 'Salvo statistiche giornaliere sito: '+site_code+' giorno: '+ str(date_to_scan.strftime("%d-%m-%Y")) +' pageviews:'+str(pageviews)+' users: '+str(users)
                p = DailyStatisticsSite(site = site, date= date_to_scan, pageviews = pageviews.encode("utf-8"), users = users.encode("utf-8"), pageviewsPerUser = pageviewsPerUser, avarangeSessionTime = str(minutes).zfill(2) +":"+str(seconds).zfill(2)  )                                    
                p.save()
                
            except Exception, e:
                print_log_exception()
                print("Errore in salvataggio dati statistiche giornaliere  "+e)
        else:
            print 'Nessun risultato trovato statistiche giornaliere'
            
    # Salva a DB nella tabella del tren sito TrendPageviews
    def save_trend(self, pageviews, site_code, date_from, date_to):    
        if pageviews:  
            try:    
                if  site_code == 'a':
                    site_url = 'www.a.it'
                elif site_code == 'b':
                    site_url = 'www.b.it'
                elif site_code == 'c':
                    site_url = 'www.c.it'   
                site = get_site(site_code)                
                # Pulisco i dati presenti a DB                
                TrendPageviews.objects.filter(site = site, from_date= date_from, to_date= date_to).delete()
                p = TrendPageviews(site = site, pageviews = pageviews, from_date= date_from, to_date= date_to)                
                p.save()
                if(log_level=="ALL" or log_level=="NORMAL"):
                    print "TREND sito "+ site_code +" da " + str(date_from.strftime("%d-%m-%Y")) + " a " + str(date_to.strftime("%d-%m-%Y")) + " sito " + site_code + " Pageviews: " + str(pageviews)
            except Exception, e:
                print_log_exception()
                print("Errore in salvataggio dati trend "+e)
        else:
            print 'Nennun risultato trovato trend'
            
    # Salva a DB nella tabella degli articoli piu visti DailyMostViewed
    def save_results_daily_most_viewed(self, results, site_code, date_to_scan):            
        if results:  
            try:     
                if(log_level=="ALL"):
                    print "Del giorno %s per il profilo %s" % ( str(date_to_scan.strftime("%d-%m-%Y")), results.get('profileInfo').get('webPropertyId'))                
                if results.get('profileInfo').get('webPropertyId') == 'UA-1':
                    site_code == 'a'
                    site_url = 'www.a.it'
                elif results.get('profileInfo').get('webPropertyId') == 'UA-2':
                    site_code == 'b'
                    site_url = 'www.b.it'
                elif results.get('profileInfo').get('webPropertyId') == 'UA-3':
                    site_code == 'c'                
                    site_url = 'www.c.it'                
                site = get_site(site_code)                
                # Pulisco i dati presenti a DB
                DailyMostViewed.objects.filter(site = site, views_date= date_to_scan).delete()
                for i in range(len(results.get('rows'))):                                                                                                             
                    # aggiunta data pubblicazione tra i dati salvati                    
                    try:
                        if(env == 'PROD'):
                            dt = self.get_published_date(site_url + results.get('rows')[i][1].encode("utf-8"))                    
                        else:
                            dt = None                            
                    except:
                        dt = None                       
                    # Salvo la riga a DB
                    if dt is not None:
                        p = DailyMostViewed(site = site, position = i+1, views_date= date_to_scan, title = results.get('rows')[i][0].encode("utf-8") , pageviews = results.get('rows')[i][2].encode("utf-8"), users = results.get('rows')[i][3].encode("utf-8"), publication_date = dt.date().strftime("%d/%m/%Y"),publication_hour = dt.time().strftime("%H:%M"),)                    
                    else:
                        p = DailyMostViewed(site = site, position = i+1, views_date= date_to_scan, title = results.get('rows')[i][0].encode("utf-8") , pageviews = results.get('rows')[i][2].encode("utf-8"), users = results.get('rows')[i][3].encode("utf-8"))
                    p.save()                    
                    if(log_level=="ALL"):
                        print 'Salvataggio dati del giorno %s con titolo %s completato.' % ( str(date_to_scan.strftime("%d-%m-%Y")), results.get('rows')[i][0].encode("utf-8") ) 
                if(log_level=="NORMAL" or log_level=="ALL"):
                    print 'Salvataggio dati articoli del giorno %s per la testata %s completato.' % ( str(date_to_scan.strftime("%d-%m-%Y")), site_code) 
            except Exception, e:
                print_log_exception()
                print("Errore in salvataggio dati articoli "+e)
        else:
            print 'Nennun risultato trovato articoli'
    
    # Estraee dal /generic-xml del singola articolo la data di pubblicazione
    def get_published_date(self, urlSite):
        try:                 
            urlXml = 'http://' + urlSite + '/generic-xml'            
            if (env == 'PROD'):
                # PROD            
                proxy = urllib2.ProxyHandler({'http': ''})
                opener = urllib2.build_opener(proxy)
                urllib2.install_opener(opener)
                con = urllib2.urlopen( urlXml )           
            if (env == 'LOCAL'):
                # Locale
                req = urllib2.Request(urlXml, headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3', 'Accept-Encoding': 'none', 'Accept-Language': 'en-US,en;q=0.8', 'Connection': 'keep-alive'}            )                         
                con = urllib2.urlopen( urlXml )                           
            
            doc = xml.dom.minidom.parse(con)                        
            pubDate = doc.getElementsByTagName('pubDate')[0].firstChild.nodeValue
            # es <pubDate>2019-01-08T06:56:15+0100</pubDate>            
            if doc.getElementsByTagName('onTime') and doc.getElementsByTagName('onTime')[0] and doc.getElementsByTagName('onTime')[0].firstChild.nodeValue:
                onTimeDate = doc.getElementsByTagName('onTime')[0].firstChild.nodeValue
                dt = parse(onTimeDate)
            else:
                dt = parse(pubDate)
            
            return dt                                   
        except Exception, e:
            print " Errore scaricando l\'URL: " + urlXml
            print_log_exception()
            
            return None
    
    # Mappa nome del sito nel codice ID GA
    def get_id_selected_site(self, nameSite, isWWW):
        
        id_code = 'UA-1' # TODO gestire caso base
        if isWWW:
            if nameSite == 'a':
                id_code = 'UA-1'
            elif nameSite == 'b':
                id_code = 'UA-2'
            elif nameSite == 'c':
                id_code = 'UA-3'      
        else:
            if nameSite == 'a':
                id_code = 'UA-11'
            elif nameSite == 'b':
                id_code = 'UA-21'
            elif nameSite == 'c':
                id_code = 'UA-31'      
        return id_code
    
         
    def unicode_decode(text):
        try:
            return text.encode('utf-8').decode()
        except UnicodeDecodeError:
            return text.encode('utf-8')
      
        
# Fine del file

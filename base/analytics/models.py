# coding: utf-8
#
# Modello dati per analytics
#

from django.db import models
from datetime import datetime, date, timedelta
from django.contrib.sites.models import Site
from django.contrib.auth.models import User
from django.conf import settings

# Articoli maggiormente visualizzati giornalmente
class DailyMostViewed(models.Model):
    
    site                            = models.ForeignKey(Site, verbose_name="Sito", help_text="Sito principale di questa testata.")
    position                        = models.CharField(blank=False, null=False, max_length = 3,  verbose_name="Posizione")        
    views_date                      = models.DateTimeField(blank=False, null=False, verbose_name='Data della statistica', help_text=u"Data della statistica.")
    title                           = models.CharField(max_length = 100,  verbose_name="Titolo")        
    users                           = models.DecimalField(decimal_places=0, null=False, max_digits=20, verbose_name="Utenti")     
    pageviews                       = models.DecimalField(decimal_places=0, null=False, max_digits=20, verbose_name="Visualizzazioni di pagina")     
    publication_date                = models.CharField(max_length = 30,  verbose_name="Data di pubblicazione")    
    publication_hour                = models.CharField(max_length = 30,  verbose_name="Ora  di pubblicazione")    

    class Meta:
        verbose_name                = "Articolo Piu Visto"
        verbose_name_plural         = "Articoli Piu Visti"
        ordering                    = ['-users']
        db_table                    = u'analytics_daily_most_viewed'
        unique_together             = (("site", "position", "views_date"), )

    def __unicode__(self):
        return self.name

    # Ritorna articolo in base alle chiavi TODO
    @staticmethod
    def get_by_code(code):
        return DailyMostViewed.objects.get(code = code)
    
    # in lowercase 
    @property
    def code_lowercase(self):
        return self.code.lower()

# Trend dei siti su GA nel tempo
class TrendPageviews(models.Model):

    site                            = models.ForeignKey(Site, verbose_name="Sito", help_text="Sito principale di questa testata.")
    from_date                       = models.DateTimeField(blank=False, null=False, verbose_name='Data inizio del trend.', help_text=u"Data inizio del periodo monitorato.")
    to_date                         = models.DateTimeField(blank=False, null=False, verbose_name='Data fine del trend.', help_text=u"Data fine del periodo monitorato.")
    pageviews                       = models.DecimalField(decimal_places=0, null=False, max_digits=20, verbose_name="Visualizzazioni di pagina nel periodo monitorato.") 
    
    class Meta:
        verbose_name                = "Pageviews nel tempo"
        verbose_name_plural         = "Pageviews nel tempo"
        ordering                    = ['-pageviews']
        db_table                    = u'analytics_trend_pageviews'
        unique_together             = (("site", "from_date", "to_date"), )
        
    def __unicode__(self):
        return self.name
    
# Statistiche giorno per giorno dei siti su GA
class DailyStatisticsSite(models.Model):

    site                            = models.ForeignKey(Site, verbose_name="Sito", help_text="Sito principale di questa testata.")
    date                            = models.DateTimeField(blank=False, null=False, verbose_name='Data analizzata.', help_text=u"Data analizzata.")
    pageviews                       = models.DecimalField(decimal_places=0, null=False, max_digits=20, verbose_name="Visualizzazioni di pagina nella data.") 
    users                           = models.DecimalField(decimal_places=0, null=False, max_digits=20, verbose_name="Utenti  nella data.") 
    pageviewsPerUser                = models.DecimalField(decimal_places=2, null=False, max_digits=10, verbose_name="Pagine viste per utente.")     
    avarangeSessionTime             = models.CharField(max_length = 20,  verbose_name="Durata media sessione.")    
    facebook_page_post_engagement   = models.DecimalField(decimal_places=2, null=True, max_digits=10, verbose_name="Facebook iterazioni con i post.")     
    
    class Meta:
        verbose_name                = "Statistica giornaliera."
        verbose_name_plural         = "Statistiche giornaliere."
        ordering                    = ['-date']
        db_table                    = u'analytics_daily_statistics'
        unique_together             = (("site", "date"), )
        
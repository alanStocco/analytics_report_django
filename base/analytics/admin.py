# coding: utf-8
#
# Admin per i modelli di questa Django Application.
#

from django.contrib import admin
from alan.analytics.models import *


# Admin per Analytics - DailyMostViewedAdmin
class DailyMostViewedAdmin(admin.ModelAdmin):
    list_display = ( 'site', 'position', 'views_date', 'title', 'users', 'pageviews' )
    search_fields = ( 'title', )
    # filter_horizontal = ( 'sites', )
    save_on_top = True
    list_per_page = 20

# Admin per Analytics - TrendPageviewsAdmin
class TrendPageviewsAdmin(admin.ModelAdmin):
    list_display = ( 'site', 'from_date', 'to_date', 'pageviews' )
    search_fields = ( 'site', 'to_date' )
    # filter_horizontal = ( 'sites', )
    save_on_top = True
    list_per_page = 20

admin.site.register(DailyMostViewed, DailyMostViewedAdmin)
admin.site.register(TrendPageviews, TrendPageviewsAdmin)


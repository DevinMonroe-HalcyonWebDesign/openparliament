import datetime
import json
import urllib, urllib2

from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.conf import settings
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404
from django.template import Context, loader, RequestContext
from django.views import generic
from django.views.decorators.vary import vary_on_headers

from parliament.core.utils import get_twitter_share_url
from parliament.hansards.models import Document, HansardCache, Statement

def _get_hansard(hansard_id, hansard_date):
    if hansard_id:
        return get_object_or_404(Document, pk=hansard_id)
    elif hansard_date:
        try:
            return Document.objects.get(date=datetime.date(*[int(x) for x in hansard_date.split('-')]))
        except Exception:
            raise Http404
    else:
        raise Exception("hansard() requires an ID or date")

@vary_on_headers('X-Requested-With')
def hansard(request, hansard_id=None, hansard_date=None, statement_seq=None):
    PER_PAGE = 15
    if 'singlepage' in request.GET:
        PER_PAGE = 1000
        
    hansard = _get_hansard(hansard_id, hansard_date)
    
    statement_qs = Statement.objects.filter(document=hansard).select_related('member__politician', 'member__riding', 'member__party')
    paginator = Paginator(statement_qs, PER_PAGE)

    highlight_statement = None
    try:
        if statement_seq is not None and 'page' not in request.GET:
            highlight_statement = int(statement_seq)
            page = int(highlight_statement/PER_PAGE) + 1
        else:
            page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    # If page request (9999) is out of range, deliver last page of results.
    try:
        statements = paginator.page(page)
    except (EmptyPage, InvalidPage):
        statements = paginator.page(paginator.num_pages)
    
    if highlight_statement is not None:
        try:
            highlight_statement = filter(lambda s: s.sequence == highlight_statement, statements.object_list)[0]
        except IndexError:
            raise Http404
        
    if request.is_ajax():
        t = loader.get_template("hansards/statement_page.inc")
    else:
        t = loader.get_template("hansards/hansard_detail.html")
    c = RequestContext(request, {
        'hansard': hansard,
        'page': statements,
        'highlight_statement': highlight_statement,
        'pagination_url': hansard.get_absolute_url(),
        'singlepage': 'singlepage' in request.GET,
    })
    return HttpResponse(t.render(c))
    
def statement_twitter(request, hansard_id, statement_seq):
    """Redirects to a Twitter page, prepopulated with sharing info for a particular statement."""
    try:
        statement = Statement.objects.get(document=hansard_id, sequence=statement_seq)
    except Statement.DoesNotExist:
        raise Http404
        
    if statement.politician:
        description = statement.politician.name
    else:
        description = statement.who
    description += ' on ' + statement.topic
    
    return HttpResponseRedirect(
        get_twitter_share_url(statement.get_absolute_url(), description)
    )
    
def statement_permalink(request, statement_seq, hansard_id=None, hansard_date=None):
    """A page displaying only a single statement. Used as a non-JS permalink."""
    
    hansard = _get_hansard(hansard_id, hansard_date)
    statement = get_object_or_404(Statement, document=hansard, sequence=statement_seq)
    
    if statement.politician:
        who = statement.politician.name
    else:
        who = statement.who
    title = who
    
    if statement.topic:
        title += u' on %s' % statement.topic
    t = loader.get_template("hansards/statement_permalink.html")
    c = RequestContext(request, {
        'title': title,
        'who': who,
        'page': {'object_list': [statement]},
        'statement': statement,
        'hansard': hansard,
        'statements_full_date': True,
        #'statements_context_link': True
    })
    return HttpResponse(t.render(c))
    
def hansardcache (request, hansard_id):
    cache = HansardCache.objects.get(document=hansard_id)
    return HttpResponse(cache.getHTML())
    
def index(request):
    return generic.date_based.archive_index(request, 
        queryset=Document.objects.all(), 
        date_field='date',
        num_latest=17,
        extra_context={'title': 'The Debates of the House of Commons'})
        
def by_year(request, year):
    return generic.date_based.archive_year(request,
        queryset=Document.objects.all().order_by('date'),
        date_field='date',
        year=year,
        make_object_list=True,
        extra_context={'title': 'Debates from %s' % year})

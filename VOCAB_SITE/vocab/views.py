import csv
from datetime import datetime
import logging
import pdb
from django.conf import settings
from django.contrib.auth import logout, login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

from django.core.urlresolvers import reverse

from django.db import transaction, IntegrityError
from django.db.models import Q

from django.forms import formset_factory
from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render

from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .forms import RegisterForm, RegisteredIRIForm, SearchForm, RequiredFormSet, VocabularyDataForm, UploadVocabularyForm
from .models import RegisteredIRI, VocabularyData
from .tasks import notify_user, update_htaccess

logger = logging.getLogger(__name__)

@csrf_protect
@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def createIRI(request):
    RegisteredIRIFormset = formset_factory(RegisteredIRIForm, formset=RequiredFormSet)
    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        formset = RegisteredIRIFormset(request.POST)
        # check whether it's valid:
        if formset.is_valid():
            # process the data in form.cleaned_data as required
            for form in formset:
                if form.is_valid():
                    vocabulary_path = form.cleaned_data['vocabulary_path']
                    termType = form.cleaned_data['term_type']
                    term = form.cleaned_data['term']
                    iriobj = RegisteredIRI.objects.create(vocabulary_path=vocabulary_path, term_type=termType, term=term, user=request.user)
            return render(request, 'iriCreationResults.html', {'newiri': iriobj.full_iri})
    # if a GET (or any other method) we'll create a blank form
    else:
        formset = RegisteredIRIFormset()
    return render(request, 'createIRI.html', {'formset': formset})

@csrf_protect
@require_http_methods(["POST", "GET"])
@transaction.atomic
def createUser(request):
    if request.method == 'GET':
        form = RegisterForm()
        return render(request, 'createUser.html', {"form": form})
    elif request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['username']
            pword = form.cleaned_data['password']
            email = form.cleaned_data['email']
            # If username doesn't already exist
            if not User.objects.filter(username__exact=name).count():
                # if email doesn't already exist
                if not User.objects.filter(email__exact=email).count():
                    user = User.objects.create_user(name, email, pword)
                else:
                    return render(request, 'createUser.html', {"form": form, "error_message": "Email %s is already registered." % email})
            else:
                return render(request, 'createUser.html', {"form": form, "error_message": "User %s already exists." % name})
            # If a user is already logged in, log them out
            if request.user.is_authenticated():
                logout(request)
            new_user = authenticate(username=name, password=pword)
            login(request, new_user)
            return HttpResponseRedirect(reverse('home'))
        else:
            return render(request, 'createUser.html', {"form": form})

@login_required
@require_http_methods(["GET"])
def userProfile(request):
    return render(request, 'userProfile.html')

@csrf_protect
@require_http_methods(["GET", "POST"])
def searchResults(request):
    if request.method == 'POST':
        form = SearchForm(request.POST)
        if form.is_valid:
            query = Q(vocabulary_path__contains=form.data['search_term']) | Q(term_type__contains=form.data['search_term']) \
                | Q(term__contains=form.data['search_term'])
            iris = RegisteredIRI.objects.filter(query & Q(accepted=True))
        return render(request, 'searchResults.html', {"form":form, "iris":iris})
    else:
        form = SearchForm()
    return render(request, 'searchResults.html', {"form":form})

@login_required()
@require_http_methods(["GET"])
def iriCreationResults(request):
    results = RegisteredIRI.objects.filter(user=request.user)
    return render(request, 'iriCreationResults.html', {'iris':results})

@login_required()
@require_http_methods(["GET", "POST"])
@transaction.atomic
def adminIRIs(request):
    if request.user.is_superuser:
        iris = RegisteredIRI.objects.filter(accepted=False, reviewed=False)
        if request.method == "GET":
            return render(request, 'adminIRIs.html', {"iris": iris})
        else:
            vocabulary = request.POST['hidden-vocabulary_path']
            term_type = request.POST['hidden-term_type']
            term = request.POST['hidden-term']
            try:
                iri = RegisteredIRI.objects.get(vocabulary_path=vocabulary, term_type=term_type, term=term)
            except RegisteredIRI.DoesNotExist as dne:
                logger.exception(dne.message)
            else:
                if request.POST['action'] == "Accept":
                    iri.accepted = True
                    iri.reviewed = True
                    update_htaccess.delay("fake title", iri.vocabulary_path, "http://jsonld-redirect", "http://html-redirect")
                else:
                    iri.reviewed = True
                iri.save()
                notify_user.delay(iri.full_iri, iri.user.email, iri.accepted)
        return render(request, 'adminIRIs.html', {"iris": iris})
    else:
        return HttpResponseForbidden()

@csrf_protect
@login_required()
@require_http_methods(["GET"])
def vocabulary(request, vocab_name):
    print vocab_name
    dispV = VocabularyData.objects.get(name=vocab_name)
    print dispV
    return render(request, 'vocabulary.html', {'vocab':vocab_name})

@csrf_protect
@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def createVocabulary(request):
    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        if 'upload' in request.POST:
            form = UploadVocabularyForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    parse_csv(request.FILES['file'], request.user)
                except Exception, e:
                    return HttpResponseBadRequest(e.message)
                return render(request, 'createVocabulary.html', {'upload_form': UploadVocabularyForm(), 'form':VocabularyDataForm(),
                    'success': 'Vocabulary successfully created'})
            else:
                return render(request, 'createVocabulary.html', {'upload_form': form, 'form': VocabularyDataForm()})
        else:
            # create a form instance and populate it with data from the request:
            form = VocabularyDataForm(request.POST)
            # check whether it's valid:
            if form.is_valid():
                # process the data in form.cleaned_data as required
                vocabName = form.cleaned_data['name']
                vocabIRI = form.cleaned_data['iri']
                vocabobj = VocabularyData.objects.create(name=vocabName, iri=vocabIRI, user=request.user)
                return render(request, 'createVocabulary.html', {'upload_form': UploadVocabularyForm(), 'form':VocabularyDataForm(),
                    'success': 'Vocabulary successfully created'})
            else:
                return render(request, 'createVocabulary.html', {'upload_form': UploadVocabularyForm(), 'form': form})
    else:
        form = VocabularyDataForm(user=request.user)
        upload_form = UploadVocabularyForm()
    return render(request, 'createVocabulary.html', {'form': form, 'upload_form': upload_form})

@require_http_methods(["GET"])
def downloadCSV(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="vocabtemplate.csv"'
    writer = csv.writer(response)
    writer.writerow(["IRI", "rdf:type", "skos:prefLabel", "skos:altLabel", "xapi:thirdPartyLabel", "xapi:closelyRelatedNaturalLanguageTerm", \
        "skos:inScheme", "xapi:referencedBy", "skos:editorialNote", "skos:definition", "skos:historyNote", "skos:broader", "skos:broadMatch", \
        "skos:narrower", "skos:narrowMatch", "skos:relatedMatch", "dcterms:created", "dcterms:modified", "foaf:name", "prov:wasGeneratedBy", \
        "prov:wasRevisionOf", "prov:specializationOf", "skos:example"])
    return response

def parse_csv(vocab_file, user):
    reader = csv.reader(vocab_file)
    data = {'base_iri': '', 'rdf_type': '', 'dcterms_created': '', 'dcterms_modified': '', 'foaf_name': '', 'prov_specializationOf': '', 'prov_wasGeneratedBy': '',
    'prov_wasRevisionOf': '', 'skos_altLabel': '', 'skos_broader': '', 'skos_broadMatch': '', 'skos_definition': '', 'skos_editorialNote': '',
    'skos_example': '', 'skos_historyNote': '', 'skos_inScheme': '', 'skos_narrower': '', 'skos_narrowMatch': '', 'skos_prefLabel': '',
    'skos_relatedMatch': '', 'skos_scopeNote': '', 'xapi_closelyRelatedNaturalLanguageTerm': '', 'xapi_referencedBy': '', 'xapi_thirdPartyLabel': ''}
    row_num = 0
    for row in reader:
        # In case first row of file is header row
        if row[0] != 'IRI':
            row_num += 1
            validate_csv_row(row, row_num, user)
            try:
                iri = RegisteredIRI.objects.create(full_iri=row[0], user=user)
            except Exception, e:
                raise Exception("Could not create IRI %s in row %s -- Error: %s" % (row[0], row_num, e.message))
            row[0] = iri
            data['base_iri'] = row[0]
            data['rdf_type'] = row[1]
            data['skos_prefLabel'] = [x.strip() for x in row[2][1:-1].split(",")]
            data['skos_altLabel'] = [x.strip() for x in row[3][1:-1].split(",")]
            data['xapi_thirdPartyLabel'] = [x.strip() for x in row[4][1:-1].split(",")]
            data['xapi_closelyRelatedNaturalLanguageTerm'] = [x.strip() for x in row[5][1:-1].split(",")]
            data['skos_inScheme'] = row[6]
            data['xapi_referencedBy'] = row[7]
            data['skos_editorialNote'] = [x.strip() for x in row[8][1:-1].split(",")]
            data['skos_scopeNote'] = [x.strip() for x in row[9][1:-1].split(",")]
            data['skos_definition'] = [x.strip() for x in row[10][1:-1].split(",")]
            data['skos_historyNote'] = [x.strip() for x in row[11][1:-1].split(",")]
            data['skos_broader'] = [x.strip() for x in row[12][1:-1].split(",")]
            data['skos_broadMatch'] = [x.strip() for x in row[13][1:-1].split(",")]
            data['skos_narrower'] = [x.strip() for x in row[14][1:-1].split(",")]
            data['skos_narrowMatch'] = [x.strip() for x in row[15][1:-1].split(",")]
            data['skos_relatedMatch'] = [x.strip() for x in row[16][1:-1].split(",")]
            pdb.set_trace()
            data['dcterms_created'] = row[17]
            data['dcterms_modified'] = row[18]
            data['foaf_name'] = [x.strip() for x in row[19][1:-1].split(",")]
            data['prov_wasGeneratedBy'] = row[20]
            data['prov_wasRevisionOf'] = [x.strip() for x in row[21][1:-1].split(",")]
            data['prov_specializationOf'] = [x.strip() for x in row[22][1:-1].split(",")]
            data['skos_example'] = [x.strip() for x in row[23][1:-1].split(",")]
            try:
                VocabularyData.objects.create(**data)
            except Exception, e:
                raise Exception("Could not create Vocabulary object in row %s -- Error: %s" % (row_num, e.message))

def validate_csv_row(row, row_num, user):
    if not row[0].startswith(settings.IRI_DOMAIN):
        raise Exception("IRI in row %s does not begin with %s" % (row_num, settings.IRI_DOMAIN))

    if RegisteredIRI.objects.filter(full_iri=row[0]).exists():
        raise Exception("IRI %s in row %s already exists" % (row[0], row_num))

    if row[17]:
        try:
            row[17] = datetime.strptime(row[17], "%m/%d/%Y")
        except ValueError as e:
            raise Exception("Error while parsing the date from dcterms:created, row %s -- Error: %s" % (row_num, e.message))

    if row[18]:
        try:
            row[18] = datetime.strptime(row[18], "%m/%d/%Y")
        except ValueError as e:
            raise Exception("Error while parsing the date from dcterms:modified, row %s -- Error: %s" % (row_num, e.message))

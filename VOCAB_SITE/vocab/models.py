from __future__ import unicode_literals

import datetime as dt
import time
import json

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.db import models, IntegrityError
from django.db.models.signals import post_save
from django.dispatch import receiver

from .tasks import notify_admins

TERM_TYPE_CHOICES = (
	('', '------'),
	('verbs', 'Verbs'),
	('activityTypes', 'Activity Types'),
	('attachments', 'Attachments'),
	('extensions', 'Extensions')
)

class RegisteredIRI(models.Model):
	vocabulary_path = models.CharField(max_length=50)
	term_type = models.CharField(max_length=15, blank=True, choices=TERM_TYPE_CHOICES)
	term = models.CharField(max_length=50, blank=True)
	accepted = models.BooleanField(default=False)
	reviewed = models.BooleanField(default=False)
	full_iri = models.URLField()
	user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)

	class Meta:
		unique_together = (("vocabulary_path", "term_type", "term", "user"), ("full_iri", "user"))

	def save(self, *args, **kwargs):
		if (self.term and not self.term_type) or (self.term and self.term_type == TERM_TYPE_CHOICES[0][1]):
			raise IntegrityError("Must supply a term type if supplying a term")
		# Automatically save full_iri if not given
		if not self.full_iri:
			if self.term_type:
				if self.term:
					self.full_iri = settings.IRI_DOMAIN + "/".join([self.vocabulary_path, self.term_type, self.term])
				else:
					self.full_iri = settings.IRI_DOMAIN + "/".join([self.vocabulary_path, self.term_type])
			else:
				self.full_iri = settings.IRI_DOMAIN + self.vocabulary_path
		else:
			path = self.full_iri[len(settings.IRI_DOMAIN):]
			parts = path.split("/")
			self.vocabulary_path = parts[0]
			if len(parts) > 1:
				if not parts[1] in [x[1] for x in TERM_TYPE_CHOICES[1:]]:
					raise Exception("Must supply a valid term type")
				self.term_type = parts[1]
				if len(parts) > 2:
					self.term = parts[2]
		super(RegisteredIRI, self).save(*args, **kwargs)

	def __unicode__(self):
		# If is for if user gets deleted somehow...
		return json.dumps({"address": self.full_iri, "user": self.user.username if self.user else 'None (Removed)' })

@receiver(post_save, sender=RegisteredIRI)
def iri_post_save(sender, **kwargs):
	if kwargs['created']:
		notify_admins.delay(kwargs['instance'].full_iri)

def vocabulary_data_file_path(instance, filename):
	date = int(time.mktime(dt.datetime.now().timetuple()))
	return 'vocabulary_data/{0}_{1}'.format(date, filename)
	
class VocabularyData(models.Model):
	base_iri = models.OneToOneField(RegisteredIRI, blank=True, null=True, on_delete=models.SET_NULL)
	rdf_type = models.CharField(max_length=250, blank=True)
	dcterms_created = models.DateTimeField(blank=True, null=True, db_index=True)
	dcterms_modified = models.DateTimeField(blank=True, null=True, db_index=True)
	foaf_name = ArrayField(models.CharField(max_length=250, blank=True), null=True)
	prov_specializationOf = ArrayField(models.CharField(max_length=250, blank=True), null=True)
	prov_wasGeneratedBy = models.CharField(max_length=250, blank=True)
	prov_wasRevisionOf = ArrayField(models.CharField(max_length=250, blank=True), null=True)
	skos_altLabel = ArrayField(models.CharField(max_length=250, blank=True), null=True)
	skos_broader = ArrayField(models.CharField(max_length=250, blank=True), null=True)
	skos_broadMatch = ArrayField(models.CharField(max_length=250, blank=True), null=True)
	skos_definition = ArrayField(models.CharField(max_length=250, blank=True), null=True)
	skos_editorialNote = ArrayField(models.CharField(max_length=250, blank=True), null=True)
	skos_example = ArrayField(models.CharField(max_length=250, blank=True), null=True)
	skos_historyNote = ArrayField(models.CharField(max_length=250, blank=True), null=True)
	skos_inScheme = models.CharField(max_length=250, blank=True)
	skos_narrower = ArrayField(models.CharField(max_length=250, blank=True), null=True)
	skos_narrowMatch = ArrayField(models.CharField(max_length=250, blank=True), null=True)
	skos_prefLabel = ArrayField(models.CharField(max_length=250, blank=True), null=True)
	skos_relatedMatch = ArrayField(models.CharField(max_length=250, blank=True), null=True)
	skos_scopeNote = ArrayField(models.CharField(max_length=250, blank=True), null=True)
	xapi_closelyRelatedNaturalLanguageTerm = ArrayField(models.CharField(max_length=250, blank=True), null=True)
	xapi_referencedBy = models.CharField(max_length=250, blank=True)
	xapi_thirdPartyLabel = ArrayField(models.CharField(max_length=250, blank=True), null=True)


	def __unicode__(self):
		# If is for if user gets deleted somehow...
		return json.dumps({"VocabularyDataIRI": self.base_iri.full_iri})

class TermTypeData(models.Model):
	name = models.CharField(max_length=250)
	vocabulary_data = models.ForeignKey(VocabularyData)

	def __unicode__(self):
		return "%s:%s" % (self.vocabulary_data.name, self.name)

class TermData(models.Model):
	name = models.CharField(max_length=250)
	term_type_data = models.ForeignKey(TermTypeData)

	def __unicode__(self):
		return "%s:%s:%s" % (self.term_type_data__vocabulary_data.name, self.term_type_data.name, self.name)
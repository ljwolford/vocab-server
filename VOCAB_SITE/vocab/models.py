from __future__ import unicode_literals

import json

from django.conf import settings
from django.contrib.auth.models import User
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
	user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)

	def return_address(self):
		if self.term_type:
			if self.term:
				return settings.IRI_DOMAIN + "/".join([self.vocabulary_path, self.term_type, self.term])
			return settings.IRI_DOMAIN + "/".join([self.vocabulary_path, self.term_type])
		return settings.IRI_DOMAIN + self.vocabulary_path

	class Meta:
		unique_together = ("vocabulary_path", "term_type", "term")

	def save(self, *args, **kwargs):
		if (self.term and not self.term_type) or (self.term and self.term_type == TERM_TYPE_CHOICES[0][1]):
			raise IntegrityError("Must supply a term type if supplying a term")
		super(RegisteredIRI, self).save(*args, **kwargs)

	def __unicode__(self):
		# If is for if user gets deleted somehow...
		return json.dumps({"address": self.return_address(), "user": self.user.username if self.user else 'None (Removed)' })

@receiver(post_save, sender=RegisteredIRI)
def iri_post_save(sender, **kwargs):
	if kwargs['created']:
		notify_admins.delay(kwargs['instance'].return_address())

class VocabularyData(models.Model):
	name = models.CharField(max_length=250)
	base_iri = models.OneToOneField(RegisteredIRI, blank=True, null=True, on_delete=models.SET_NULL)
	editorialNote = models.TextField()
	# what about copName, copUrl, dateCreated, dateModified, revisionNum, numTerms

	def __unicode__(self):
		return "%s" % (self.id, self.name)

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

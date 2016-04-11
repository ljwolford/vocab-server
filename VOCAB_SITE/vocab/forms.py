from django import forms
from django.forms import ModelForm
from django.forms.formsets import BaseFormSet

from .models import RegisteredIRI, VocabularyData

class RegisterForm(forms.Form):
    username = forms.CharField(max_length=200, label='Name')
    email = forms.EmailField(max_length=200, label='Email')
    password = forms.CharField(label='Password',
                                widget=forms.PasswordInput(render_value=False))
    password2 = forms.CharField(label='Password Again',
                                widget=forms.PasswordInput(render_value=False))

    def clean(self):
        cleaned = super(RegisterForm, self).clean()
        p1 = cleaned.get("password")
        p2 = cleaned.get("password2")
        if p1 and p2:
            if p1 == p2:
                return cleaned
        raise forms.ValidationError("Passwords did not match")

class ContactForm(forms.Form):
    subject = forms.CharField(label='Subject', max_length=100)
    message = forms.CharField(widget=forms.Textarea)
    sender = forms.EmailField()
    cc_myself = forms.BooleanField(required=False)

class SearchForm(forms.Form):
    search_term = forms.CharField(label='Search:', max_length=100)

class RegisteredIRIForm(ModelForm):
    class Meta:
        model = RegisteredIRI
        fields = ['vocabulary_path', 'term_type', 'term']
        widgets = {
            'vocabulary_path': forms.TextInput(attrs={'placeholder': 'Vocabulary/Profile', 'class': 'pure-input-1-2'}),
            'term_type': forms.Select(attrs={'placeholder': 'Term Type', 'class': 'pure-input-1-2'}),
            'term': forms.TextInput(attrs={'placeholder': 'Term', 'class': 'pure-input-1-2'})
        }

    def clean(self):
        cleaned = super(RegisteredIRIForm, self).clean()
        term_type = cleaned.get("term_type", None)
        term = cleaned.get("term", None)
        if term and not term_type:
            raise forms.ValidationError("Must have a term type if giving a term")
        return cleaned

class RequiredFormSet(BaseFormSet):
    def __init__(self, *args, **kwargs):
        super(RequiredFormSet, self).__init__(*args, **kwargs)
        for form in self.forms:
            form.empty_permitted = False


    def clean(self):
        cleaned = super(RequiredFormSet, self).clean()
        form = self.forms[0]
        total = int(form.data['form-TOTAL_FORMS'])
        tuple_list = []
        for x in range(0, total):
            data_tuple = (form.data['form-'+str(x)+'-vocabulary_path'], form.data['form-'+str(x)+'-term_type'], \
                form.data['form-'+str(x)+'-term'])
            if data_tuple in tuple_list:
                raise forms.ValidationError("Forms cannot have the same triple values as other forms in the form set")
            else:
                tuple_list.append(data_tuple)

class VocabularyDataForm(forms.ModelForm):
    # vocabName = forms.CharField(label='Vocabulary Name', max_length=100)
    # vocabIRI = forms.URLField(label='Vocabulary IRI', max_length=100)
    class Meta:
        model = VocabularyData
        fields = '__all__'

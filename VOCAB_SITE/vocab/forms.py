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
    class Meta:
        model = VocabularyData
        exclude = ['payload']

    def __init__(self, user=None, **kwargs):
        super(VocabularyDataForm, self).__init__(**kwargs)
        if user:
            self.fields['base_iri'].queryset = RegisteredIRI.objects.filter(user=user)

class UploadVocabularyForm(forms.Form):
    file = forms.FileField(label='Vocabulary CSV:')

    def clean(self):
        cleaned = super(UploadVocabularyForm, self).clean()
        if not 'file' in cleaned:
            return cleaned
        file_name = cleaned.get("file").name
        if not file_name.endswith('.csv'):
            raise forms.ValidationError("File must end with .csv")
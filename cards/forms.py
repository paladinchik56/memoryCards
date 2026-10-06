from django import forms

from .models import Card, Collection


class CardForm(forms.ModelForm):
    class Meta:
        model = Card
        fields = ['question', 'answer', 'collection']
        widgets = {
            'question': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Question (LaTeX formulas coming later)',
            }),
            'answer': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Answer (LaTeX formulas coming later)',
            }),
        }
        labels = {'question': 'Question', 'answer': 'Answer', 'collection': 'Collection'}

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        # Scope the dropdown to this user's own collections -- besides
        # being the only sensible choice to show, this also stops someone
        # from filing a card into another user's collection by tampering
        # with the POST data: Django's ModelChoiceField rejects any
        # submitted value that isn't in `queryset`.
        self.fields['collection'].queryset = Collection.objects.filter(owner=user) if user else Collection.objects.none()
        self.fields['collection'].required = False
        self.fields['collection'].empty_label = 'No collection'

    def clean_question(self):
        question = self.cleaned_data['question'].strip()
        if not question:
            raise forms.ValidationError('Question cannot be empty.')

        duplicates = Card.objects.filter(user=self.user, question=question)
        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError('You already have a card with this question.')

        return question

    def clean_answer(self):
        answer = self.cleaned_data['answer'].strip()
        if not answer:
            raise forms.ValidationError('Answer cannot be empty.')
        return answer


class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = ['name', 'description', 'visibility']
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Description (optional)',
            }),
        }
        labels = {
            'name': 'Name',
            'description': 'Description',
            'visibility': 'Visibility',
        }

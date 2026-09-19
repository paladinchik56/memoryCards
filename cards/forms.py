from django import forms

from .models import Card


class CardForm(forms.ModelForm):
    class Meta:
        model = Card
        fields = ['question', 'answer']
        widgets = {
            'question': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Вопрос (позже сюда добавим формулы LaTeX)',
            }),
            'answer': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Ответ (позже сюда добавим формулы LaTeX)',
            }),
        }
        labels = {'question': 'Вопрос', 'answer': 'Ответ'}

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_question(self):
        question = self.cleaned_data['question'].strip()
        if not question:
            raise forms.ValidationError('Вопрос не может быть пустым.')

        duplicates = Card.objects.filter(user=self.user, question=question)
        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError('У вас уже есть карточка с таким вопросом.')

        return question

    def clean_answer(self):
        answer = self.cleaned_data['answer'].strip()
        if not answer:
            raise forms.ValidationError('Ответ не может быть пустым.')
        return answer

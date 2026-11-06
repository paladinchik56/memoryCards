// Flip-and-grade behaviour shared by the review and topic-run screens.
// Click/tap the card or press Space/Enter/↑/↓ to flip; once the answer is
// shown, → grades "right" and ← grades "wrong" (same as the buttons).
(function () {
    const card = document.getElementById('flashcard-inner');
    const gradeForm = document.getElementById('grade-form');
    if (!card || !gradeForm) return;

    let submitted = false;
    const flip = () => {
        card.classList.toggle('flipped');
        gradeForm.hidden = !gradeForm.hidden;
    };
    const grade = (value) => {
        if (submitted || gradeForm.hidden) return;
        submitted = true;
        gradeForm.requestSubmit(gradeForm.querySelector(`button[name="correct"][value="${value}"]`));
    };

    card.addEventListener('click', flip);
    gradeForm.addEventListener('submit', () => { submitted = true; });

    document.addEventListener('keydown', (e) => {
        const t = e.target;
        if (e.altKey || e.ctrlKey || e.metaKey || t.isContentEditable ||
            ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName)) return;
        if (e.key === 'ArrowRight') { e.preventDefault(); grade('1'); }
        else if (e.key === 'ArrowLeft') { e.preventDefault(); grade('0'); }
        else if ([' ', 'Enter', 'ArrowUp', 'ArrowDown'].includes(e.key) && t.tagName !== 'BUTTON' && t.tagName !== 'A') {
            e.preventDefault(); flip();
        }
    });
})();

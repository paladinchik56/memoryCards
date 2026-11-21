// Small behaviours of the website: formulas, the study card, selection, dialogs.
(function () {
    'use strict';

    // Formulas: $$…$$ and \[…\] (block), \(…\) (inline). A single $ is NOT a
    // formula, so shell cards like "$HOME" stay as they are.
    function renderMath(root) {
        if (!window.renderMathInElement) return;
        window.renderMathInElement(root, {
            delimiters: [
                { left: '$$', right: '$$', display: true },
                { left: '\\[', right: '\\]', display: true },
                { left: '\\(', right: '\\)', display: false },
            ],
            throwOnError: false,
            ignoredTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code', 'option'],
        });
    }
    renderMath(document.body);

    // Study card: click / Space to flip; once flipped, → right, ← wrong, or swipe.
    const card = document.getElementById('flashcard');
    if (card) {
        const grade = document.querySelector('.grade');
        const right = document.getElementById('right-form');
        const wrong = document.getElementById('wrong-form');
        const stampR = card.querySelector('.stamp.right');
        const stampW = card.querySelector('.stamp.wrong');
        let sent = false;
        const flip = () => {
            card.classList.toggle('flipped');
            if (grade) grade.classList.toggle('shown', card.classList.contains('flipped'));
        };
        const send = (ok) => {
            if (sent || !card.classList.contains('flipped')) return;
            sent = true;
            card.style.transition = 'transform .18s ease';
            card.style.transform = `translateX(${ok ? 140 : -140}%) rotate(${ok ? 12 : -12}deg)`;
            setTimeout(() => (ok ? right : wrong).submit(), 160);
        };

        let startX = null, dx = 0, dragged = false;
        card.addEventListener('pointerdown', (e) => {
            if (!card.classList.contains('flipped')) return;
            startX = e.clientX; dx = 0; dragged = false;
        });
        window.addEventListener('pointermove', (e) => {
            if (startX === null) return;
            dx = e.clientX - startX;
            if (Math.abs(dx) > 6) dragged = true;
            card.style.transform = `translateX(${dx}px) rotate(${dx / 25}deg)`;
            if (stampR) stampR.style.opacity = Math.max(0, Math.min(1, dx / 110));
            if (stampW) stampW.style.opacity = Math.max(0, Math.min(1, -dx / 110));
        });
        window.addEventListener('pointerup', () => {
            if (startX === null) return;
            startX = null;
            if (Math.abs(dx) > 110) return send(dx > 0);
            card.style.transform = '';
            if (stampR) stampR.style.opacity = 0;
            if (stampW) stampW.style.opacity = 0;
        });
        card.addEventListener('click', () => { if (!dragged) flip(); dragged = false; });

        document.addEventListener('keydown', (e) => {
            const tag = e.target.tagName;
            if (e.altKey || e.ctrlKey || e.metaKey || ['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) return;
            if (e.key === 'ArrowRight') { e.preventDefault(); send(true); }
            else if (e.key === 'ArrowLeft') { e.preventDefault(); send(false); }
            else if ([' ', 'Enter', 'ArrowUp', 'ArrowDown'].includes(e.key) && tag !== 'BUTTON' && tag !== 'A' && tag !== 'SUMMARY') {
                e.preventDefault(); flip();
            }
        });
    }

    // Clickable table rows.
    document.querySelectorAll('tr[data-href]').forEach((tr) => {
        tr.addEventListener('click', () => { window.location = tr.dataset.href; });
    });

    // "Select all" in deck editing.
    document.querySelectorAll('[data-select-all]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const boxes = document.querySelectorAll(btn.dataset.selectAll);
            const all = Array.from(boxes).every((b) => b.checked);
            boxes.forEach((b) => { b.checked = !all; });
        });
    });

    // Skip/reset dialog: "apply to all" mirrors one choice onto every card.
    const applyAll = document.getElementById('apply-all');
    if (applyAll) {
        document.querySelectorAll('.conflict input[type=radio]').forEach((r) => {
            r.addEventListener('change', () => {
                if (!applyAll.checked) return;
                document.querySelectorAll(`.conflict input[type=radio][value="${r.value}"]`).forEach((o) => { o.checked = true; });
            });
        });
    }

    // Copy share link.
    document.querySelectorAll('[data-copy]').forEach((btn) => {
        btn.addEventListener('click', () => {
            navigator.clipboard.writeText(document.querySelector(btn.dataset.copy).textContent.trim())
                .then(() => { btn.textContent = '✓'; });
        });
    });

    // Confirm before destructive submits.
    document.querySelectorAll('[data-confirm]').forEach((el) => {
        el.addEventListener('click', (e) => { if (!window.confirm(el.dataset.confirm)) e.preventDefault(); });
    });

    // Appearance (profile).
    document.querySelectorAll('[data-appearance]').forEach((sel) => {
        let current = 'system';
        try { current = localStorage.getItem('appearance') || 'system'; } catch (e) {}
        sel.value = current;
        sel.addEventListener('change', () => {
            try { localStorage.setItem('appearance', sel.value); } catch (e) {}
            if (sel.value === 'system') document.documentElement.removeAttribute('data-theme');
            else document.documentElement.setAttribute('data-theme', sel.value);
        });
    });

    // Submit a form when its select changes (language).
    document.querySelectorAll('select[data-autosubmit]').forEach((s) => {
        s.addEventListener('change', () => s.form.submit());
    });
})();

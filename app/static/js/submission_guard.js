(function () {
    "use strict";

    const lockedForms = new WeakSet();
    const originalButtonContent = new WeakMap();

    function preserveSubmitterValue(form, submitter) {
        if (!submitter || !submitter.name || submitter.disabled) {
            return;
        }
        const hiddenInput = document.createElement("input");
        hiddenInput.type = "hidden";
        hiddenInput.name = submitter.name;
        hiddenInput.value = submitter.value;
        hiddenInput.dataset.submissionGuardValue = "true";
        form.appendChild(hiddenInput);
    }

    function setBusyState(control) {
        control.disabled = true;
        control.setAttribute("aria-disabled", "true");
        if (control.tagName === "BUTTON") {
            originalButtonContent.set(control, control.innerHTML);
            control.innerHTML = '<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>Wird gespeichert …';
        } else {
            originalButtonContent.set(control, control.value);
            control.value = "Wird gespeichert …";
        }
    }

    function restoreControl(control) {
        control.disabled = false;
        control.removeAttribute("aria-disabled");
        const originalContent = originalButtonContent.get(control);
        if (originalContent === undefined) {
            return;
        }
        if (control.tagName === "BUTTON") {
            control.innerHTML = originalContent;
        } else {
            control.value = originalContent;
        }
        originalButtonContent.delete(control);
    }

    function lock(form, submitter) {
        if (!form || lockedForms.has(form)) {
            return false;
        }
        lockedForms.add(form);
        form.dataset.submitting = "true";
        preserveSubmitterValue(form, submitter);
        form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(setBusyState);
        return true;
    }

    function unlock(form) {
        if (!form || !lockedForms.has(form)) {
            return;
        }
        lockedForms.delete(form);
        delete form.dataset.submitting;
        form.querySelectorAll('[data-submission-guard-value="true"]').forEach(function (input) {
            input.remove();
        });
        form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(restoreControl);
    }

    document.addEventListener("submit", function (event) {
        const form = event.target;
        if (
            !(form instanceof HTMLFormElement)
            || form.method.toLowerCase() === "get"
            || form.dataset.allowRepeatedSubmit === "true"
        ) {
            return;
        }
        if (lockedForms.has(form)) {
            event.preventDefault();
            event.stopImmediatePropagation();
            return;
        }
        if (event.defaultPrevented) {
            return;
        }
        lock(form, event.submitter);
    });

    window.PfotenSubmitGuard = {lock: lock, unlock: unlock};
})();

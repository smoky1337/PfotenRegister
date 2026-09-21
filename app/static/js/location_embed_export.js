(function () {
    "use strict";

    function initializeLocationEmbedExport() {
        const locationInputs = Array.from(document.querySelectorAll("[data-embed-location]"));
        const generateButton = document.getElementById("generateLocationEmbedCode");
        const copyButton = document.getElementById("copyLocationEmbedCode");
        const codeOutput = document.getElementById("locationEmbedCode");
        const status = document.getElementById("locationEmbedStatus");

        if (!generateButton || !copyButton || !codeOutput || !status) {
            return;
        }

        function setSelection(checked) {
            locationInputs.forEach(function (input) {
                input.checked = checked;
            });
        }

        function selectedLocationIds() {
            return locationInputs
                .filter(function (input) { return input.checked; })
                .map(function (input) { return Number(input.value); });
        }

        async function generateCode() {
            const locationIds = selectedLocationIds();
            if (!locationIds.length) {
                status.textContent = "Bitte mindestens einen aktiven Standort auswählen.";
                return;
            }

            const originalContent = generateButton.innerHTML;
            generateButton.disabled = true;
            generateButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>Code wird erzeugt …';
            copyButton.disabled = true;

            try {
                const response = await fetch(generateButton.dataset.endpoint, {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({location_ids: locationIds})
                });
                const payload = await response.json();
                if (!response.ok) {
                    throw new Error(payload.error || "Der Einbettungscode konnte nicht erzeugt werden.");
                }
                codeOutput.value = payload.code;
                copyButton.disabled = false;
                status.textContent = `Code für ${payload.location_count} Standort${payload.location_count === 1 ? "" : "e"} erzeugt.`;
            } catch (error) {
                codeOutput.value = "";
                status.textContent = error.message;
            } finally {
                generateButton.disabled = false;
                generateButton.innerHTML = originalContent;
            }
        }

        async function copyCode() {
            if (!codeOutput.value) {
                return;
            }
            try {
                await navigator.clipboard.writeText(codeOutput.value);
            } catch (error) {
                codeOutput.focus();
                codeOutput.select();
                document.execCommand("copy");
            }
            status.textContent = "Einbettungscode wurde in die Zwischenablage kopiert.";
        }

        document.getElementById("selectAllEmbedLocations")?.addEventListener("click", function () {
            setSelection(true);
        });
        document.getElementById("clearEmbedLocations")?.addEventListener("click", function () {
            setSelection(false);
        });
        generateButton.addEventListener("click", generateCode);
        copyButton.addEventListener("click", copyCode);
    }

    document.addEventListener("DOMContentLoaded", initializeLocationEmbedExport);
})();

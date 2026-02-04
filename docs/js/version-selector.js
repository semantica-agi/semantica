document.addEventListener("DOMContentLoaded", function () {
    // Target the header title
    var headerTitle = document.querySelector(".md-header__title");

    if (headerTitle) {
        // Create the container for the version selector
        var versionContainer = document.createElement("div");
        versionContainer.className = "version-scroll-container";

        // Create dropdown wrapper
        var versionDropdown = document.createElement("div");
        versionDropdown.className = "version-dropdown";

        // Define versions with latest 0.2.6 on top
        var versions = [
            { name: "0.2.6", url: "#", current: true },
            { name: "0.2.5", url: "#", current: false },
            { name: "0.2.4", url: "#", current: false },
            { name: "0.2.3", url: "#", current: false },
            { name: "0.2.2", url: "#", current: false },
            { name: "0.2.1", url: "#", current: false },
            { name: "0.2.0", url: "#", current: false },
            { name: "0.1.1", url: "#", current: false },
            { name: "0.1.0", url: "#", current: false }
        ];

        // Create the toggle button showing current version
        var versionToggle = document.createElement("div");
        versionToggle.className = "version-toggle active";
        versionToggle.textContent = versions[0].name;

        // Create the dropdown list
        var versionList = document.createElement("div");
        versionList.className = "version-list";

        versions.forEach(function (version) {
            var versionLink = document.createElement("a");
            versionLink.className = "version-tag" + (version.current ? " active" : "");
            versionLink.href = version.url;
            versionLink.textContent = version.name;
            versionList.appendChild(versionLink);
        });

        // Assemble the dropdown
        versionDropdown.appendChild(versionToggle);
        versionDropdown.appendChild(versionList);
        versionContainer.appendChild(versionDropdown);

        // Insert after the header title
        headerTitle.parentNode.insertBefore(versionContainer, headerTitle.nextSibling);
    }
});

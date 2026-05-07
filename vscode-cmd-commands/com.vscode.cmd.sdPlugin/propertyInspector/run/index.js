/**
 * Property inspector for the VSCode Cmd Commands action.
 *
 * `$settings` is a Proxy installed by action.js when didReceiveSettings
 * arrives — assigning to it auto-persists via debounced setSettings. The
 * Proxy only fires on top-level property assignment, so mutating a nested
 * array in place will NOT save — always reassign `$settings.commands`.
 *
 * Title is owned by StreamDock's standard key panel (UserTitleEnabled=true
 * in manifest.json), not by this Property Inspector.
 */

const $local = false, $back = false,
    $dom = {
        main: $('.sdpi-wrapper'),
        container: $('#commands-container'),
        addBtn: $('#add-command'),
    };

let commands = [];

function renderRows() {
    $dom.container.innerHTML = '';
    commands.forEach((value, idx) => {
        const row = document.createElement('div');
        row.className = 'cmd-row';

        const num = document.createElement('span');
        num.className = 'cmd-index';
        num.textContent = (idx + 1) + '.';

        const input = document.createElement('input');
        input.type = 'text';
        input.value = value;
        input.placeholder = 'e.g. npm run build';
        input.addEventListener('input', () => {
            commands[idx] = input.value;
            commit();
        });

        const remove = document.createElement('button');
        remove.type = 'button';
        remove.textContent = '×';
        remove.title = 'remove';
        remove.addEventListener('click', () => {
            commands.splice(idx, 1);
            renderRows();
            commit();
        });

        row.appendChild(num);
        row.appendChild(input);
        row.appendChild(remove);
        $dom.container.appendChild(row);
    });
}

function commit() {
    // Reassign to trigger the $settings Proxy `set` trap (mutation alone
    // doesn't fire). saveData on action.js is itself deferred via debounce.
    $settings.commands = commands.slice();
}

const $propEvent = {
    didReceiveSettings(data) {
        const current = (data && data.settings) ? data.settings : {};
        commands = Array.isArray(current.commands) ? current.commands.slice() : [];
        renderRows();
    },
    sendToPropertyInspector() {},
    didReceiveGlobalSettings() {},
};

$dom.addBtn.addEventListener('click', () => {
    commands.push('');
    renderRows();
    commit();
});

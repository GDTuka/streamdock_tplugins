/**
 * Property inspector for the VSCode Open Project action.
 *
 * `$settings` is a Proxy installed by action.js when didReceiveSettings
 * arrives — assigning to a top-level property auto-persists via debounced
 * setSettings. Mutating nested values does NOT fire the trap.
 *
 * Title is owned by StreamDock's standard key panel (UserTitleEnabled=true),
 * not by this Property Inspector.
 */

const $local = false, $back = false,
    $dom = {
        main: $('.sdpi-wrapper'),
        path: $('#path'),
    };

const $propEvent = {
    didReceiveSettings(data) {
        const current = (data && data.settings) ? data.settings : {};
        $dom.path.value = current.path || '';
    },
    sendToPropertyInspector() {},
    didReceiveGlobalSettings() {},
};

$dom.path.addEventListener('input', () => {
    $settings.path = $dom.path.value;
});

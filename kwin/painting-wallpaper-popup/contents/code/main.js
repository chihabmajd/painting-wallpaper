// Wayland clients cannot position their own windows, so KWin does it:
// anchor the painting popup to the bottom-right of the usable area (panels excluded)
// and keep it out of the taskbar, pager and Alt+Tab.
const APP_ID = "painting-wallpaper";
const GAP = 20;

function anchor(w) {
    const area = workspace.clientArea(KWin.PlacementArea, w);
    const g = w.frameGeometry;
    const x = area.x + area.width - g.width - GAP;
    const y = area.y + area.height - g.height - GAP;
    if (g.x !== x || g.y !== y)
        w.frameGeometry = { x: x, y: y, width: g.width, height: g.height };
}

function manage(w) {
    if (!w || w.resourceClass !== APP_ID)
        return;
    w.skipTaskbar = true;
    w.skipPager = true;
    w.skipSwitcher = true;
    anchor(w);
    // the card can resize once its text is laid out: stay anchored
    w.frameGeometryChanged.connect(() => anchor(w));
}

workspace.windowList().forEach(manage);
workspace.windowAdded.connect(manage);

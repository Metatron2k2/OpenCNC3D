/* Loopback fixture driving the production launcher, updater and extractor. */
#include <stdio.h>
#include <string.h>
static char fixture_site[256];
#include "../../launcher/lcfg.h"
#undef LCFG_BASE
#define LCFG_BASE fixture_site
#define main launcher_entry
#include "../../launcher/launcher.c"
#undef main
#include "../../launcher/lupdate.c"

int main(int argc, char **argv)
{
    if (argc == 3 && !strcmp(argv[1], "offer")) {
        L_App app;
        memset(&app, 0, sizeof app);
        snprintf(app.dir, sizeof app.dir, "%s", argv[2]);
        printf("offer=%d\n", l_install_offer(&app));
        return 0;
    }
    if (argc < 3) return 2;
    snprintf(fixture_site, sizeof fixture_site, "%s", argv[1]);
    if (argc == 4 && !strcmp(argv[2], "ui-install")) {
        L_App app;
        int turns;
        memset(&app, 0, sizeof app);
        snprintf(app.dir, sizeof app.dir, "%s", argv[3]);
        app.mod[0].name = "Dawn3D"; app.mod[1].name = "RA3D";
        app.media = lm_create(app.dir, NULL);
        app.up = lu_create(app.dir, NULL);
        app.install_offer = 1;
        l_i_start(&app);
        for (turns = 0; turns < 6000 && app.m_running; turns++) {
            l_i_tick(&app); SDL_Delay(10);
        }
        printf("UI-INSTALL|phase=%d|offer=%d|reason=%s\n", app.i_phase, app.install_offer, app.i_reason);
        lu_destroy(app.fresh); lu_destroy(app.up); lm_destroy(app.media);
        return app.i_phase == LM_DONE && !app.install_offer ? 0 : 1;
    }
    return launcher_entry(argc - 1, argv + 1);
}

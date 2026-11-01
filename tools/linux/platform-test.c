/* Exercise production discovery and update parsing with local, asset-free inputs. */
#include "../../game/brain_path.h"
#include "../../launcher/lmodule.h"
#include "../../launcher/lupdate.c"
#include <assert.h>
#include <dlfcn.h>

int main(int argc, char **argv)
{
    char err[512] = {0};
    if (argc > 1 && !strcmp(argv[1], "discover")) {
        const char *path = opencnc3d_find_brain(argc > 2 ? argv[2] : NULL);
        void *brain = dlopen(path, RTLD_NOW | RTLD_LOCAL);
        if (!brain) { fprintf(stderr, "%s: %s\n", path, dlerror()); return 1; }
        assert(dlsym(brain, "CNC_Init"));
        puts(path);
        dlclose(brain);
        return 0;
    }
    if (argc > 2 && !strcmp(argv[1], "module")) {
        printf("td=%d|ra=%d\n", lmod_td_present(argv[2]), lmod_ra_present(argv[2], err, sizeof err));
        return 0;
    }
    assert(!strcmp(OPENCNC3D_PLATFORM, "linux"));
    LU_State state;
    memset(&state, 0, sizeof state);
    state.lock = SDL_CreateMutex();
    assert(state.lock);
    strcpy(state.installed, "0.0.0");
    const char *mixed = "{\"latest\":{\"tag\":\"v2.0.0\",\"assets\":["
        "{\"id\":20,\"name\":\"OpenCNC3D-macos-v2.0.0.zip\"}]},\"releases\":["
        "{\"tag\":\"v1.0.0\",\"assets\":[{\"id\":10,\"name\":\"OpenCNC3D-linux-v1.0.0.zip\",\"size\":100}]}]}";
    assert(lu_read_builds(&state, mixed, err, sizeof err));
    assert(state.full.id == 10 && !strcmp(state.latest, "1.0.0"));
    assert(!lu_read_builds(&state,
        "{\"latest\":{\"tag\":\"v2.0.0\",\"assets\":["
        "{\"id\":20,\"name\":\"OpenCNC3D-macos-v2.0.0.zip\"}]}}", err, sizeof err));
    assert(strstr(err, "linux build"));
    strcpy(state.want, "2.0.0");
    assert(!lu_read_builds(&state, mixed, err, sizeof err));
    SDL_DestroyMutex(state.lock);

    const char *feed = "{\"latest\":{\"tag\":\"v1.0.0\",\"assets\":["
        "{\"id\":11,\"name\":\"OpenCNC3D-module-td-linux-v1.0.0.zip\",\"size\":100},"
        "{\"id\":12,\"name\":\"OpenCNC3D-module-td-macos-v1.0.0.zip\",\"size\":100}]}}";
    const char *catalog = "modules 1\nversion 1.0.0\n"
        "module td macos OpenCNC3D-module-td-macos-v1.0.0.zip 100 aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
        "module td linux OpenCNC3D-module-td-linux-v1.0.0.zip 100 bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n";
    LMOD_Catalog modules;
    assert(lmod_catalog_read("1.0.0", feed, catalog, &modules, err, sizeof err));
    assert(modules.module[0].available && modules.module[0].id == 11);
    assert(!lmod_catalog_read("1.0.0", feed,
        "modules 1\nversion 1.0.0\nmodule td macos OpenCNC3D-module-td-macos-v1.0.0.zip 100 aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n",
        &modules, err, sizeof err));
    puts("LINUX-PLATFORM|PASS|release-selection|foreign-package-rejection|module-catalog");
    return 0;
}

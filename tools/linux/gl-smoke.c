/* Exercise the actual SDL/OpenGL desktop seam without game assets. */
#include <SDL.h>
#include <GL/gl.h>
#include <stdio.h>

int main(void)
{
    SDL_Window *window;
    SDL_GLContext context;
    unsigned char pixel[4] = {0};
    if (SDL_Init(SDL_INIT_VIDEO)) goto fail;
    SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 0);
    window = SDL_CreateWindow("OpenCNC3D Linux graphics check", 0, 0, 64, 64,
                              SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    if (!window) goto fail;
    context = SDL_GL_CreateContext(window);
    if (!context) { SDL_DestroyWindow(window); goto fail; }
    glClearColor(0.25f, 0.5f, 0.75f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);
    glReadPixels(0, 0, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel);
    printf("GLSMOKE|backend=%s|renderer=%s|version=%s|pixel=%u,%u,%u\n",
           SDL_GetCurrentVideoDriver(), glGetString(GL_RENDERER), glGetString(GL_VERSION),
           pixel[0], pixel[1], pixel[2]);
    int ok = glGetError() == GL_NO_ERROR && pixel[0] >= 60 && pixel[0] <= 68
          && pixel[1] >= 124 && pixel[1] <= 132 && pixel[2] >= 187 && pixel[2] <= 195;
    SDL_GL_DeleteContext(context);
    SDL_DestroyWindow(window);
    SDL_Quit();
    return ok ? 0 : 1;
fail:
    fprintf(stderr, "GLSMOKE|FAIL|%s\n", SDL_GetError());
    SDL_Quit();
    return 1;
}

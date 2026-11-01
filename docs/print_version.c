#include "10d_game.h"

#include <inttypes.h>
#include <stdio.h>

int main(void)
{
    printf("%" PRIu32 ".%" PRIu32 ".%" PRIu32 "\n",
           xdgame_version_major(),
           xdgame_version_minor(),
           xdgame_version_patch());
}

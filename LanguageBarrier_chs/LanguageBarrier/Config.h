// [LOCALIZATION-BANNER] Fork for the ROBOTICS;NOTES DaSH Simplified Chinese patch.
// Forked from CommitteeOfZero/LanguageBarrier (base commit cc982fd9),
// maintained at https://github.com/Syun1524/RND_Chinese
// See FORK-NOTES.md for the full change list. For upstream, use the CoZ repo.
#ifndef __CONFIG_H__
#define __CONFIG_H__

#include "LanguageBarrier.h"
#include "lbjson.h"

#ifdef DEFINE_CONFIG
#define CONFIG_GLOBAL
#else
#define CONFIG_GLOBAL extern
#endif

namespace lb {
CONFIG_GLOBAL json config;
void configInit();
const std::string configGetGameName();
const std::string configGetPatchName();
}  // namespace lb

#endif  // !__CONFIG_H__

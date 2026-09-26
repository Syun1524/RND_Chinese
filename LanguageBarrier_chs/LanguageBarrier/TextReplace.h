// [LOCALIZATION-BANNER] Fork for the ROBOTICS;NOTES DaSH Simplified Chinese patch.
// Forked from CommitteeOfZero/LanguageBarrier (base commit cc982fd9),
// maintained at https://github.com/Syun1524/RND_Chinese
// See FORK-NOTES.md for the full change list. For upstream, use the CoZ repo.
#ifndef __TEXTREPLACE_H__
#define __TEXTREPLACE_H__

namespace lb {
void globalTextReplacementsInit();
const char* processTextReplacements(const char* base, int fileId, int stringId);
}  // namespace lb

#endif

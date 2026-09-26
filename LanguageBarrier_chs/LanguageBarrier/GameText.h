// [LOCALIZATION-BANNER] Fork for the ROBOTICS;NOTES DaSH Simplified Chinese patch.
// Forked from CommitteeOfZero/LanguageBarrier (base commit cc982fd9),
// maintained at https://github.com/Syun1524/RND_Chinese
// See FORK-NOTES.md for the full change list. For upstream, use the CoZ repo.
#ifndef __GAMETEXT_H__
#define __GAMETEXT_H__

#include <cstdint>
#include "LanguageBarrier.h"

#ifndef GAMETEXT_H_IMPORT
#define GAMETEXT_H_IMPORT extern
#endif

namespace lb {
LB_GLOBAL uint8_t FIRST_FONT_ID;
LB_GLOBAL float COORDS_MULTIPLIER;
LB_GLOBAL uint8_t FONT_CELL_WIDTH;
LB_GLOBAL uint8_t FONT_CELL_HEIGHT;
LB_GLOBAL uint8_t FONT_ROW_LENGTH;
static const uint16_t TOTAL_NUM_FONT_CELLS = 8000;
LB_GLOBAL uint16_t GLYPH_RANGE_FULLWIDTH_START;
// TODO: make this JSON-configurable in some manner
static const uint16_t MAX_PROCESSED_STRING_LENGTH = 2000;
LB_GLOBAL uint16_t DEFAULT_LINE_LENGTH;
LB_GLOBAL uint16_t DEFAULT_MAX_CHARACTERS;
LB_GLOBAL float SGHD_LINK_UNDERLINE_GLYPH_X;
LB_GLOBAL float SGHD_LINK_UNDERLINE_GLYPH_Y;
// Careful: this also messes with the speaker markers (for spoken lines) and
// highlight in the backlog
// Taken care of with ccBacklogNamePosAdjustHook
LB_GLOBAL int DIALOGUE_REDESIGN_YOFFSET_SHIFT;
LB_GLOBAL int DIALOGUE_REDESIGN_LINEHEIGHT_SHIFT;
LB_GLOBAL bool HAS_BACKLOG_UNDERLINE;
LB_GLOBAL int8_t BACKLOG_HIGHLIGHT_DEFAULT_HEIGHT;
LB_GLOBAL int8_t BACKLOG_HIGHLIGHT_HEIGHT_SHIFT;
LB_GLOBAL float OUTLINE_PADDING;
LB_GLOBAL uint8_t OUTLINE_CELL_WIDTH;
LB_GLOBAL uint8_t OUTLINE_CELL_HEIGHT;
// arbitrarily chosen; I hope the game doesn't try to use this
LB_GLOBAL uint16_t OUTLINE_TEXTURE_ID;
static const int LINECOUNT_DISABLE_OR_ERROR = 0xFF;
static const uint8_t NOT_A_LINK = 0xFF;
LB_GLOBAL int SGHD_PHONE_X_PADDING;
LB_GLOBAL uint16_t GLYPH_ID_FULLWIDTH_SPACE;
LB_GLOBAL uint16_t GLYPH_ID_HALFWIDTH_SPACE;
LB_GLOBAL bool HAS_DOUBLE_GET_SC3_STRING_DISPLAY_WIDTH;
LB_GLOBAL bool HAS_DRAW_PHONE_TEXT;
LB_GLOBAL bool HAS_SGHD_PHONE;
LB_GLOBAL bool HAS_GET_SC3_STRING_LINE_COUNT;
LB_GLOBAL bool HAS_RINE;
LB_GLOBAL bool RINE_BLACK_NAMES;
LB_GLOBAL bool NEEDS_CLEARLIST_TEXT_POSITION_ADJUST;
LB_GLOBAL bool NEEDS_CC_BACKLOG_NAME_POS_ADJUST;
LB_GLOBAL bool IMPROVE_DIALOGUE_OUTLINES;
LB_GLOBAL bool HAS_SPLIT_FONT;
LB_GLOBAL bool TIP_REIMPL;
LB_GLOBAL int TIP_REIMPL_GLYPH_SIZE;
LB_GLOBAL int TIP_REIMPL_LINE_LENGTH;
LB_GLOBAL bool CC_BACKLOG_HIGHLIGHT;
LB_GLOBAL float CC_BACKLOG_HIGHLIGHT_SPRITE_Y;
LB_GLOBAL float CC_BACKLOG_HIGHLIGHT_SPRITE_HEIGHT;
LB_GLOBAL float CC_BACKLOG_HIGHLIGHT_HEIGHT_SHIFT;
LB_GLOBAL float CC_BACKLOG_HIGHLIGHT_YOFFSET_SHIFT;
// SC3 keeps controls and glyphs apart in the raw stream: a control is a single
// low byte (<0x80), while a glyph is a two-byte big-endian value whose high
// byte has 0x80 set. The ruby (furigana) markers are the single-byte controls
// 0x09/0x0A/0x0B. The glyphs for charset index 9/10/11 -- '8', '9' and 'A' in
// the Chinese charset -- are the unrelated two-byte pairs
// 0x80 0x09 / 0x80 0x0A / 0x80 0x0B.
//
// The old check tested the *glyph* pairs as if they were ruby markers and so
// silently ate every literal '8'/'9'/'A' (e.g. "2010/9/11" -> "2010/ /11"); the
// digit '9' (0x80 0x0A) was hit unconditionally. Real ruby is single-byte and
// was never matched by that check, so rendering the three pairs as glyphs fixes
// the digits without touching any genuine ruby. Default OFF; set
// patch.rubyMarkers=true only if a locale needs the old glyph-as-marker path.
LB_GLOBAL bool RUBY_MARKERS_ENABLED;

// Dialogue ruby (annotation) horizontal placement.
//
// The page arrays that reach the draw hook carry no ruby markers, so the base
// run an annotation belongs to has to be recovered from geometry. The run is
// the tail of the preceding line whose width best matches the annotation's,
// searched inward from the line end -- the same "fit the annotation over the
// glyphs it covers" rule the engine applies when it lays the pair out.
//
// The previous rule assumed the run was exactly as many glyphs as the
// annotation has characters, which only holds for one-to-one rubies. A wide
// annotation over a few glyphs (「可靠的右手」<- "Favorite Right Arm") fell
// back to centring over the whole line and drifted a third of a line left.
// RUBY_DIALOGUE_FIT=false restores that behaviour. RUBY_DEBUG dumps one line
// per ruby run to log.txt.
LB_GLOBAL bool RUBY_DIALOGUE_FIT;
LB_GLOBAL bool RUBY_DEBUG;

// Backlog speaker-name / body column.
//
// The game centres each row's "speaker icon + name" block, so a name's right
// edge -- and the body after it -- moves with the name's length, and narration
// rows (no name at all) start further left still.
//
// Names are right-aligned to one shared column instead, and narration starts at
// that same column, so quoted dialogue and prose share one left edge. The
// column is the widest name's natural right edge: anchoring there means no name
// is ever pushed further left than the game itself put it, which is what would
// collide with the speaker icon.
//
// The array written is BacklogTextPos[], in the units the draw loop reads
// (xPosition = startX * COORDS_MULTIPLIER + BacklogTextPos[i]). Values are
// absolute -- accumulating into this cross-frame array is what made an earlier
// attempt drift every frame. BACKLOG_NAME_ALIGN=false restores the game's own
// centring. BACKLOG_NAME_DEBUG dumps one line per row to log.txt.
LB_GLOBAL bool BACKLOG_NAME_ALIGN;
// Space between a right-aligned speaker name and the body that follows it,
// in BacklogTextPos units. Without it the body butts against the name.
LB_GLOBAL int BACKLOG_BODY_GAP;
LB_GLOBAL bool BACKLOG_NAME_DEBUG;

// Dump every rnDrawText call (args + decoded text) to log.txt.
LB_GLOBAL bool RN_DRAW_TEXT_DEBUG;

// Dump every drawSingleTextLine call (args + decoded text) to log.txt. Used to
// find which call site draws a given screen's numbers, since the fixes in
// singleTextLineFixes are keyed by the caller's return address.
LB_GLOBAL bool SINGLE_LINE_DEBUG;

// Dump every drawSprite call (args) to log.txt. Used to find which call site
// blits a given atlas region, since spriteFixes is keyed by return address.
LB_GLOBAL bool SPRITE_DEBUG;

// Dump every sg0DrawGlyph2 call that lands in a given screen region (args) to
// log.txt. Used to find which call site renders a screen's digits.
LB_GLOBAL bool GLYPH_DEBUG;

// The game's language flag (0 = Japanese, 1 = English), read from the exe's own
// global. NULL until gameTextInit runs, so always null-check before dereferencing.
// Exposed because a few assets differ per language (see fileRedirection).
LB_GLOBAL int* gameExeLanguage;

// Per-call-site horizontal shifts for drawTwipoContent, keyed by the return
// address of the caller (see twipoContentFixes in patchdef.json).
//
// The phone mail header draws its field captions and its right-anchored date
// block through this one shared routine. Captions are placed at a hard-coded x
// while the date block is measured from the right edge, so a translation that
// widens the date pushes it left into the caption. A negative dx pulls the
// affected caption out of the way. TWIPO_CONTENT_DEBUG dumps each hit to
// log.txt.
LB_GLOBAL bool TWIPO_CONTENT_DEBUG;

// Allow a line break between CJK/fullwidth characters, and at the boundary
// between a CJK character and a Latin word.
//
// The tokeniser only cuts a word at a space or when the accumulated width
// exceeds the line length, and the renderer then moves that whole word to the
// next line. A space followed by a long CJK run therefore makes that run one
// indivisible block -- the run moves down as a unit and leaves most of the
// previous line empty (a TIPS entry read "既视感（法：Deja" / "vu）。指明明…",
// with the first line only a quarter full).
//
// With this on, a break opportunity is also created between adjacent CJK
// characters and at a CJK/Latin boundary, so a CJK run wraps per character.
// Latin runs stay atomic either way. Punctuation that may not open a line is
// pushed back onto the previous line instead of being stranded. Default off;
// set patch.cjkLineBreak=true to enable.
LB_GLOBAL bool CJK_LINE_BREAK;

GAMETEXT_H_IMPORT int* BacklogLineSave;
GAMETEXT_H_IMPORT int* BacklogDispLinePos;
GAMETEXT_H_IMPORT int* BacklogLineBufSize;
GAMETEXT_H_IMPORT int16_t* BacklogTextPos;
GAMETEXT_H_IMPORT int* BacklogLineBufUse;
GAMETEXT_H_IMPORT uint16_t* BacklogText;
GAMETEXT_H_IMPORT int* BacklogDispCurPosSX;
GAMETEXT_H_IMPORT int* BacklogDispCurPosEY;
GAMETEXT_H_IMPORT int* BacklogLineBufStartp;
GAMETEXT_H_IMPORT unsigned char* BacklogTextSize;
GAMETEXT_H_IMPORT int* BacklogLineBufEndp;
GAMETEXT_H_IMPORT int* BacklogBufStartp;
GAMETEXT_H_IMPORT int* MesFontColor;
GAMETEXT_H_IMPORT int* BacklogBufUse;
GAMETEXT_H_IMPORT int* BacklogDispCurPosEX;
GAMETEXT_H_IMPORT int* BacklogDispLineSize;
GAMETEXT_H_IMPORT int* BacklogDispPos;
GAMETEXT_H_IMPORT int* dword_948628;
GAMETEXT_H_IMPORT uint8_t* BacklogTextCo;
GAMETEXT_H_IMPORT int* BacklogLineVoice;
GAMETEXT_H_IMPORT int* BacklogDispLinePosY;
GAMETEXT_H_IMPORT int* BacklogDispCurPosSY;

void gameTextInit();
void fixSkipRN();
void fixLeadingZeroes();
int __cdecl getSc3StringDisplayWidthHook(char* sc3string,
                                         unsigned int maxCharacters,
                                         int baseGlyphSize);
int __cdecl drawSpriteHook(int textureId, float spriteX, float spriteY,
                           float spriteWidth, float spriteHeight,
                           float displayX, float displayY, int color,
                           int opacity, int shaderId);
}  // namespace lb

#endif  // !__GAMETEXT_H__

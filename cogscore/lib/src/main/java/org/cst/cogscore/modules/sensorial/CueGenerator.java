/*
 * Click nbfs://nbhost/SystemFileSystem/Templates/Licenses/license-default.txt to change this license
 * Click nbfs://nbhost/SystemFileSystem/Templates/Classes/Class.java to edit this template
 */
package org.modules.sensorial;

// modules/sensorial/CueGenerator.java

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

/**
 * Cue generation and application for Sperling-inspired partial-report tests.
 *
 * In the original Sperling paradigm, a cue selects a subset of the stimulus to be reported.
 * Here, a cue selects a subset of the buffer representation to be evaluated.
 *
 * This file provides:
 * - Cue<T>: immutable cue that can extract a subset from a full representation
 * - Generator<T>: produces cues (typically random) given a reference representation
 * - Ready-to-use generators for common modalities: sonar, vision, distance, position
 */
public final class CueGenerator {

    private CueGenerator() { }

    /**
     * A cue is a deterministic selector that extracts a subset from a full representation.
     * The same cue MUST be applied to both the buffer content and the ground-truth snapshot.
     */
    public interface Cue<T> {
        T extract(T full);
        String describe();
    }

    /**
     * Produces a cue, usually randomized, based on the reference representation dimensions.
     * The reference is typically the ground truth snapshot captured at t0.
     */
    public interface Generator<T> {
        Cue<T> sample(Random rnd, T reference);
        String name();
    }

    /* =======================================================================
     * SONAR (double[16] or List<Double>)
     * ======================================================================= */

    /**
     * Creates a cue generator that selects a contiguous window from a sonar vector.
     *
     * @param windowSize number of elements to select (e.g., 3 or 4)
     */
    public static Generator<double[]> sonarContiguousWindow(final int windowSize) {
        if (windowSize <= 0) throw new IllegalArgumentException("windowSize must be > 0");
        return new Generator<double[]>() {
            @Override
            public Cue<double[]> sample(Random rnd, double[] reference) {
                if (reference == null) throw new IllegalArgumentException("reference == null");
                if (reference.length < windowSize) {
                    throw new IllegalArgumentException("reference.length < windowSize");
                }
                int start = rnd.nextInt(reference.length - windowSize + 1);
                return new SonarWindowCue(start, windowSize);
            }

            @Override
            public String name() {
                return "sonarContiguousWindow(" + windowSize + ")";
            }
        };
    }

    /**
     * Creates a cue generator that selects a contiguous window from a sonar list.
     * This is useful when your buffers are stored as ArrayList<Double>.
     */
    public static Generator<List<Double>> sonarContiguousWindowList(final int windowSize) {
        if (windowSize <= 0) throw new IllegalArgumentException("windowSize must be > 0");
        return new Generator<List<Double>>() {
            @Override
            public Cue<List<Double>> sample(Random rnd, List<Double> reference) {
                if (reference == null) throw new IllegalArgumentException("reference == null");
                if (reference.size() < windowSize) {
                    throw new IllegalArgumentException("reference.size() < windowSize");
                }
                int start = rnd.nextInt(reference.size() - windowSize + 1);
                return new SonarWindowCueList(start, windowSize);
            }

            @Override
            public String name() {
                return "sonarContiguousWindowList(" + windowSize + ")";
            }
        };
    }

    private static final class SonarWindowCue implements Cue<double[]> {
        private final int start;
        private final int len;

        private SonarWindowCue(int start, int len) {
            this.start = start;
            this.len = len;
        }

        @Override
        public double[] extract(double[] full) {
            if (full == null) return null;
            double[] out = new double[len];
            System.arraycopy(full, start, out, 0, len);
            return out;
        }

        @Override
        public String describe() {
            return "SonarWindow[start=" + start + ",len=" + len + "]";
        }
    }

    private static final class SonarWindowCueList implements Cue<List<Double>> {
        private final int start;
        private final int len;

        private SonarWindowCueList(int start, int len) {
            this.start = start;
            this.len = len;
        }

        @Override
        public List<Double> extract(List<Double> full) {
            if (full == null) return null;
            List<Double> out = new ArrayList<>(len);
            for (int i = 0; i < len; i++) {
                out.add(full.get(start + i));
            }
            return out;
        }

        @Override
        public String describe() {
            return "SonarWindowList[start=" + start + ",len=" + len + "]";
        }
    }

    /* =======================================================================
     * VISION (float[H][W][3] or byte[H][W][3])
     * ======================================================================= */

    /**
     * Creates a cue generator that selects a rectangular patch from a float RGB image [H][W][C].
     *
     * @param patchH patch height
     * @param patchW patch width
     */
    public static Generator<float[][][]> visionPatchFloat(final int patchH, final int patchW) {
        if (patchH <= 0 || patchW <= 0) throw new IllegalArgumentException("patch sizes must be > 0");
        return new Generator<float[][][]>() {
            @Override
            public Cue<float[][][]> sample(Random rnd, float[][][] reference) {
                if (reference == null) throw new IllegalArgumentException("reference == null");
                int H = reference.length;
                int W = reference[0].length;
                if (H < patchH || W < patchW) {
                    throw new IllegalArgumentException("image smaller than patch");
                }
                int y0 = rnd.nextInt(H - patchH + 1);
                int x0 = rnd.nextInt(W - patchW + 1);
                return new VisionPatchCueFloat(y0, x0, patchH, patchW);
            }

            @Override
            public String name() {
                return "visionPatchFloat(" + patchH + "x" + patchW + ")";
            }
        };
    }

    /**
     * Creates a cue generator that selects a rectangular patch from a byte RGB image [H][W][C].
     */
    public static Generator<byte[][][]> visionPatchByte(final int patchH, final int patchW) {
        if (patchH <= 0 || patchW <= 0) throw new IllegalArgumentException("patch sizes must be > 0");
        return new Generator<byte[][][]>() {
            @Override
            public Cue<byte[][][]> sample(Random rnd, byte[][][] reference) {
                if (reference == null) throw new IllegalArgumentException("reference == null");
                int H = reference.length;
                int W = reference[0].length;
                if (H < patchH || W < patchW) {
                    throw new IllegalArgumentException("image smaller than patch");
                }
                int y0 = rnd.nextInt(H - patchH + 1);
                int x0 = rnd.nextInt(W - patchW + 1);
                return new VisionPatchCueByte(y0, x0, patchH, patchW);
            }

            @Override
            public String name() {
                return "visionPatchByte(" + patchH + "x" + patchW + ")";
            }
        };
    }

    private static final class VisionPatchCueFloat implements Cue<float[][][]> {
        private final int y0, x0, h, w;

        private VisionPatchCueFloat(int y0, int x0, int h, int w) {
            this.y0 = y0; this.x0 = x0; this.h = h; this.w = w;
        }

        @Override
        public float[][][] extract(float[][][] full) {
            if (full == null) return null;
            float[][][] patch = new float[h][w][];
            for (int y = 0; y < h; y++) {
                for (int x = 0; x < w; x++) {
                    patch[y][x] = full[y0 + y][x0 + x].clone();
                }
            }
            return patch;
        }

        @Override
        public String describe() {
            return "VisionPatchFloat[y0=" + y0 + ",x0=" + x0 + ",h=" + h + ",w=" + w + "]";
        }
    }

    private static final class VisionPatchCueByte implements Cue<byte[][][]> {
        private final int y0, x0, h, w;

        private VisionPatchCueByte(int y0, int x0, int h, int w) {
            this.y0 = y0; this.x0 = x0; this.h = h; this.w = w;
        }

        @Override
        public byte[][][] extract(byte[][][] full) {
            if (full == null) return null;
            byte[][][] patch = new byte[h][w][];
            for (int y = 0; y < h; y++) {
                for (int x = 0; x < w; x++) {
                    patch[y][x] = full[y0 + y][x0 + x].clone();
                }
            }
            return patch;
        }

        @Override
        public String describe() {
            return "VisionPatchByte[y0=" + y0 + ",x0=" + x0 + ",h=" + h + ",w=" + w + "]";
        }
    }

    /* =======================================================================
     * DISTANCE/DEPTH (float[H][W] or byte[H][W])
     * ======================================================================= */

    /**
     * Creates a cue generator that selects a rectangular patch from a float distance map [H][W].
     */
    public static Generator<float[][]> distancePatchFloat(final int patchH, final int patchW) {
        if (patchH <= 0 || patchW <= 0) throw new IllegalArgumentException("patch sizes must be > 0");
        return new Generator<float[][]>() {
            @Override
            public Cue<float[][]> sample(Random rnd, float[][] reference) {
                if (reference == null) throw new IllegalArgumentException("reference == null");
                int H = reference.length;
                int W = reference[0].length;
                if (H < patchH || W < patchW) {
                    throw new IllegalArgumentException("map smaller than patch");
                }
                int y0 = rnd.nextInt(H - patchH + 1);
                int x0 = rnd.nextInt(W - patchW + 1);
                return new DistancePatchCueFloat(y0, x0, patchH, patchW);
            }

            @Override
            public String name() {
                return "distancePatchFloat(" + patchH + "x" + patchW + ")";
            }
        };
    }

    /**
     * Creates a cue generator that selects a rectangular patch from a byte distance map [H][W].
     */
    public static Generator<byte[][]> distancePatchByte(final int patchH, final int patchW) {
        if (patchH <= 0 || patchW <= 0) throw new IllegalArgumentException("patch sizes must be > 0");
        return new Generator<byte[][]>() {
            @Override
            public Cue<byte[][]> sample(Random rnd, byte[][] reference) {
                if (reference == null) throw new IllegalArgumentException("reference == null");
                int H = reference.length;
                int W = reference[0].length;
                if (H < patchH || W < patchW) {
                    throw new IllegalArgumentException("map smaller than patch");
                }
                int y0 = rnd.nextInt(H - patchH + 1);
                int x0 = rnd.nextInt(W - patchW + 1);
                return new DistancePatchCueByte(y0, x0, patchH, patchW);
            }

            @Override
            public String name() {
                return "distancePatchByte(" + patchH + "x" + patchW + ")";
            }
        };
    }

    private static final class DistancePatchCueFloat implements Cue<float[][]> {
        private final int y0, x0, h, w;

        private DistancePatchCueFloat(int y0, int x0, int h, int w) {
            this.y0 = y0; this.x0 = x0; this.h = h; this.w = w;
        }

        @Override
        public float[][] extract(float[][] full) {
            if (full == null) return null;
            float[][] patch = new float[h][w];
            for (int y = 0; y < h; y++) {
                System.arraycopy(full[y0 + y], x0, patch[y], 0, w);
            }
            return patch;
        }

        @Override
        public String describe() {
            return "DistancePatchFloat[y0=" + y0 + ",x0=" + x0 + ",h=" + h + ",w=" + w + "]";
        }
    }

    private static final class DistancePatchCueByte implements Cue<byte[][]> {
        private final int y0, x0, h, w;

        private DistancePatchCueByte(int y0, int x0, int h, int w) {
            this.y0 = y0; this.x0 = x0; this.h = h; this.w = w;
        }

        @Override
        public byte[][] extract(byte[][] full) {
            if (full == null) return null;
            byte[][] patch = new byte[h][w];
            for (int y = 0; y < h; y++) {
                System.arraycopy(full[y0 + y], x0, patch[y], 0, w);
            }
            return patch;
        }

        @Override
        public String describe() {
            return "DistancePatchByte[y0=" + y0 + ",x0=" + x0 + ",h=" + h + ",w=" + w + "]";
        }
    }

    /* =======================================================================
     * POSITION (float[10] or double[10])
     * ======================================================================= */

    /**
     * A simple cue generator for position buffers:
     * it randomly chooses to query translation-only, orientation-only, or both.
     *
     * Convention expected by the default cue:
     * - translation at indices [0..2]
     * - quaternion at indices [3..6] in (w,x,y,z) order
     * Remaining indices [7..] are ignored by default cues.
     */
    public static Generator<float[]> positionFloat() {
        return new Generator<float[]>() {
            @Override
            public Cue<float[]> sample(Random rnd, float[] reference) {
                if (reference == null) throw new IllegalArgumentException("reference == null");
                if (reference.length < 7) throw new IllegalArgumentException("position buffer must have length >= 7");
                int mode = rnd.nextInt(3);
                if (mode == 0) return new PositionCueFloat(PositionCueMode.TRANSLATION_ONLY);
                if (mode == 1) return new PositionCueFloat(PositionCueMode.ORIENTATION_ONLY);
                return new PositionCueFloat(PositionCueMode.TRANSLATION_AND_ORIENTATION);
            }

            @Override
            public String name() {
                return "positionFloat(randomMode)";
            }
        };
    }

    public static Generator<double[]> positionDouble() {
        return new Generator<double[]>() {
            @Override
            public Cue<double[]> sample(Random rnd, double[] reference) {
                if (reference == null) throw new IllegalArgumentException("reference == null");
                if (reference.length < 7) throw new IllegalArgumentException("position buffer must have length >= 7");
                int mode = rnd.nextInt(3);
                if (mode == 0) return new PositionCueDouble(PositionCueMode.TRANSLATION_ONLY);
                if (mode == 1) return new PositionCueDouble(PositionCueMode.ORIENTATION_ONLY);
                return new PositionCueDouble(PositionCueMode.TRANSLATION_AND_ORIENTATION);
            }

            @Override
            public String name() {
                return "positionDouble(randomMode)";
            }
        };
    }

    public enum PositionCueMode {
        TRANSLATION_ONLY,
        ORIENTATION_ONLY,
        TRANSLATION_AND_ORIENTATION
    }

    private static final class PositionCueFloat implements Cue<float[]> {
        private final PositionCueMode mode;

        private PositionCueFloat(PositionCueMode mode) {
            this.mode = mode;
        }

        @Override
        public float[] extract(float[] full) {
            if (full == null) return null;
            switch (mode) {
                case TRANSLATION_ONLY:
                    return new float[]{full[0], full[1], full[2]};
                case ORIENTATION_ONLY:
                    return new float[]{full[3], full[4], full[5], full[6]};
                default:
                    return new float[]{full[0], full[1], full[2], full[3], full[4], full[5], full[6]};
            }
        }

        @Override
        public String describe() {
            return "PositionCueFloat[" + mode + "]";
        }
    }

    private static final class PositionCueDouble implements Cue<double[]> {
        private final PositionCueMode mode;

        private PositionCueDouble(PositionCueMode mode) {
            this.mode = mode;
        }

        @Override
        public double[] extract(double[] full) {
            if (full == null) return null;
            switch (mode) {
                case TRANSLATION_ONLY:
                    return new double[]{full[0], full[1], full[2]};
                case ORIENTATION_ONLY:
                    return new double[]{full[3], full[4], full[5], full[6]};
                default:
                    return new double[]{full[0], full[1], full[2], full[3], full[4], full[5], full[6]};
            }
        }

        @Override
        public String describe() {
            return "PositionCueDouble[" + mode + "]";
        }
    }
}
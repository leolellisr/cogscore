/*
 * Click nbfs://nbhost/SystemFileSystem/Templates/Licenses/license-default.txt to change this license
 * Click nbfs://nbhost/SystemFileSystem/Templates/Classes/Class.java to edit this template
 */
package org.modules.sensorial;

/**
 *
 * @author leolellisr
 */
// modules/sensorial/FidelityMetric.java

import java.util.List;

/**
 * Distance and normalization for fidelity computation.
 *
 * The runner computes:
 * fidelity = 1 - (distance / maxDistance)
 *
 * A Metric<T> must provide:
 * - distance between two subset representations
 * - an upper bound maxDistance used to normalize
 *
 * This file includes ready-to-use metrics for:
 * - sonar vectors (RMSE)
 * - vision tensors (MSE)
 * - distance maps (MSE)
 * - position/orientation (translation RMSE + quaternion geodesic angle)
 */
public final class FidelityMetric {

    private FidelityMetric() { }

    public interface Metric<T> {
        double distance(T storedSubset, T truthSubset);
        double maxDistance();
        String name();
    }

    /* =======================================================================
     * SONAR (double[] and List<Double>)
     * ======================================================================= */

    /**
     * RMSE for sonar vectors with known value range [minVal, maxVal].
     * RMSE is bounded by (maxVal - minVal), which becomes maxDistance().
     */
    public static Metric<double[]> sonarRmse(final double minVal, final double maxVal) {
        if (maxVal <= minVal) throw new IllegalArgumentException("maxVal must be > minVal");
        final double range = maxVal - minVal;
        return new Metric<double[]>() {
            @Override
            public double distance(double[] a, double[] b) {
                if (a == null || b == null) return Double.NaN;
                if (a.length != b.length) throw new IllegalArgumentException("length mismatch");
                double sum = 0.0;
                for (int i = 0; i < a.length; i++) {
                    double d = a[i] - b[i];
                    sum += d * d;
                }
                return Math.sqrt(sum / a.length);
            }

            @Override
            public double maxDistance() {
                return range;
            }

            @Override
            public String name() {
                return "sonarRmse([" + minVal + "," + maxVal + "])";
            }
        };
    }

    /**
     * RMSE for sonar lists with known value range [minVal, maxVal].
     */
    public static Metric<List<Double>> sonarRmseList(final double minVal, final double maxVal) {
        if (maxVal <= minVal) throw new IllegalArgumentException("maxVal must be > minVal");
        final double range = maxVal - minVal;
        return new Metric<List<Double>>() {
            @Override
            public double distance(List<Double> a, List<Double> b) {
                if (a == null || b == null) return Double.NaN;
                if (a.size() != b.size()) throw new IllegalArgumentException("size mismatch");
                double sum = 0.0;
                for (int i = 0; i < a.size(); i++) {
                    double d = a.get(i) - b.get(i);
                    sum += d * d;
                }
                return Math.sqrt(sum / a.size());
            }

            @Override
            public double maxDistance() {
                return range;
            }

            @Override
            public String name() {
                return "sonarRmseList([" + minVal + "," + maxVal + "])";
            }
        };
    }

    /* =======================================================================
     * VISION (float[][][] and byte[][][])
     * ======================================================================= */

    /**
     * MSE for float RGB tensors. Assumes values in [minVal, maxVal].
     * The MSE upper bound is (maxVal-minVal)^2.
     */
    public static Metric<float[][][]> visionMseFloat(final double minVal, final double maxVal) {
        if (maxVal <= minVal) throw new IllegalArgumentException("maxVal must be > minVal");
        final double range = maxVal - minVal;
        final double maxMse = range * range;
        return new Metric<float[][][]>() {
            @Override
            public double distance(float[][][] a, float[][][] b) {
                if (a == null || b == null) return Double.NaN;
                int H = a.length;
                int W = a[0].length;
                int C = a[0][0].length;
                if (b.length != H || b[0].length != W || b[0][0].length != C) {
                    throw new IllegalArgumentException("shape mismatch");
                }
                double sum = 0.0;
                long n = 0;
                for (int y = 0; y < H; y++) {
                    for (int x = 0; x < W; x++) {
                        for (int c = 0; c < C; c++) {
                            double d = a[y][x][c] - b[y][x][c];
                            sum += d * d;
                            n++;
                        }
                    }
                }
                return sum / (double) n;
            }

            @Override
            public double maxDistance() {
                return maxMse;
            }

            @Override
            public String name() {
                return "visionMseFloat([" + minVal + "," + maxVal + "])";
            }
        };
    }

    /**
     * MSE for byte RGB tensors. Assumes bytes encode [0..255].
     * The MSE upper bound is 255^2.
     */
    public static Metric<byte[][][]> visionMseByte() {
        final double maxMse = 255.0 * 255.0;
        return new Metric<byte[][][]>() {
            @Override
            public double distance(byte[][][] a, byte[][][] b) {
                if (a == null || b == null) return Double.NaN;
                int H = a.length;
                int W = a[0].length;
                int C = a[0][0].length;
                if (b.length != H || b[0].length != W || b[0][0].length != C) {
                    throw new IllegalArgumentException("shape mismatch");
                }
                double sum = 0.0;
                long n = 0;
                for (int y = 0; y < H; y++) {
                    for (int x = 0; x < W; x++) {
                        for (int c = 0; c < C; c++) {
                            int av = a[y][x][c] & 0xFF;
                            int bv = b[y][x][c] & 0xFF;
                            double d = av - bv;
                            sum += d * d;
                            n++;
                        }
                    }
                }
                return sum / (double) n;
            }

            @Override
            public double maxDistance() {
                return maxMse;
            }

            @Override
            public String name() {
                return "visionMseByte([0,255])";
            }
        };
    }

    /* =======================================================================
     * DISTANCE/DEPTH (float[][] and byte[][])
     * ======================================================================= */

    /**
     * MSE for float distance maps. Assumes values in [minVal, maxVal].
     * Upper bound is (maxVal-minVal)^2.
     */
    public static Metric<float[][]> distanceMseFloat(final double minVal, final double maxVal) {
        if (maxVal <= minVal) throw new IllegalArgumentException("maxVal must be > minVal");
        final double range = maxVal - minVal;
        final double maxMse = range * range;
        return new Metric<float[][]>() {
            @Override
            public double distance(float[][] a, float[][] b) {
                if (a == null || b == null) return Double.NaN;
                int H = a.length;
                int W = a[0].length;
                if (b.length != H || b[0].length != W) {
                    throw new IllegalArgumentException("shape mismatch");
                }
                double sum = 0.0;
                long n = 0;
                for (int y = 0; y < H; y++) {
                    for (int x = 0; x < W; x++) {
                        double d = a[y][x] - b[y][x];
                        sum += d * d;
                        n++;
                    }
                }
                return sum / (double) n;
            }

            @Override
            public double maxDistance() {
                return maxMse;
            }

            @Override
            public String name() {
                return "distanceMseFloat([" + minVal + "," + maxVal + "])";
            }
        };
    }

    /**
     * MSE for byte distance maps. Assumes bytes encode [0..255].
     */
    public static Metric<byte[][]> distanceMseByte() {
        final double maxMse = 255.0 * 255.0;
        return new Metric<byte[][]>() {
            @Override
            public double distance(byte[][] a, byte[][] b) {
                if (a == null || b == null) return Double.NaN;
                int H = a.length;
                int W = a[0].length;
                if (b.length != H || b[0].length != W) {
                    throw new IllegalArgumentException("shape mismatch");
                }
                double sum = 0.0;
                long n = 0;
                for (int y = 0; y < H; y++) {
                    for (int x = 0; x < W; x++) {
                        int av = a[y][x] & 0xFF;
                        int bv = b[y][x] & 0xFF;
                        double d = av - bv;
                        sum += d * d;
                        n++;
                    }
                }
                return sum / (double) n;
            }

            @Override
            public double maxDistance() {
                return maxMse;
            }

            @Override
            public String name() {
                return "distanceMseByte([0,255])";
            }
        };
    }

    /* =======================================================================
     * POSITION (float[] or double[]; supports translation-only, orientation-only, or both)
     * ======================================================================= */

    /**
     * Position/orientation metric for float arrays extracted by the default position cues:
     * - length == 3: translation only
     * - length == 4: quaternion only (w,x,y,z)
     * - length >= 7: translation (first 3) + quaternion (next 4)
     *
     * Translation part is normalized by posRange (max expected positional error).
     * Orientation part is normalized by pi (max geodesic angle).
     *
     * maxDistance = wPos + wOri.
     */
    public static Metric<float[]> positionFloat(final double posRange, final double wPos, final double wOri) {
        if (posRange <= 0) throw new IllegalArgumentException("posRange must be > 0");
        if (wPos < 0 || wOri < 0) throw new IllegalArgumentException("weights must be >= 0");
        final double maxD = wPos + wOri;
        if (maxD <= 0) throw new IllegalArgumentException("wPos + wOri must be > 0");

        return new Metric<float[]>() {
            @Override
            public double distance(float[] a, float[] b) {
                if (a == null || b == null) return Double.NaN;
                if (a.length != b.length) throw new IllegalArgumentException("length mismatch");

                double dPos = 0.0;
                double dOri = 0.0;

                if (a.length == 3) {
                    dPos = rmse3(a, b) / posRange;
                    return wPos * clamp01(dPos);
                }

                if (a.length == 4) {
                    dOri = quatAngle(a, b) / Math.PI;
                    return wOri * clamp01(dOri);
                }

                if (a.length >= 7) {
                    dPos = rmse3(a, b) / posRange;
                    dOri = quatAngle(
                            new float[]{a[3], a[4], a[5], a[6]},
                            new float[]{b[3], b[4], b[5], b[6]}
                    ) / Math.PI;
                    return wPos * clamp01(dPos) + wOri * clamp01(dOri);
                }

                throw new IllegalArgumentException("Unsupported position subset length: " + a.length);
            }

            @Override
            public double maxDistance() {
                return maxD;
            }

            @Override
            public String name() {
                return "positionFloat(posRange=" + posRange + ",wPos=" + wPos + ",wOri=" + wOri + ")";
            }
        };
    }

    public static Metric<double[]> positionDouble(final double posRange, final double wPos, final double wOri) {
        if (posRange <= 0) throw new IllegalArgumentException("posRange must be > 0");
        if (wPos < 0 || wOri < 0) throw new IllegalArgumentException("weights must be >= 0");
        final double maxD = wPos + wOri;
        if (maxD <= 0) throw new IllegalArgumentException("wPos + wOri must be > 0");

        return new Metric<double[]>() {
            @Override
            public double distance(double[] a, double[] b) {
                if (a == null || b == null) return Double.NaN;
                if (a.length != b.length) throw new IllegalArgumentException("length mismatch");

                double dPos;
                double dOri;

                if (a.length == 3) {
                    dPos = rmse3(a, b) / posRange;
                    return wPos * clamp01(dPos);
                }

                if (a.length == 4) {
                    dOri = quatAngle(a, b) / Math.PI;
                    return wOri * clamp01(dOri);
                }

                if (a.length >= 7) {
                    dPos = rmse3(a, b) / posRange;
                    dOri = quatAngle(
                            new double[]{a[3], a[4], a[5], a[6]},
                            new double[]{b[3], b[4], b[5], b[6]}
                    ) / Math.PI;
                    return wPos * clamp01(dPos) + wOri * clamp01(dOri);
                }

                throw new IllegalArgumentException("Unsupported position subset length: " + a.length);
            }

            @Override
            public double maxDistance() {
                return maxD;
            }

            @Override
            public String name() {
                return "positionDouble(posRange=" + posRange + ",wPos=" + wPos + ",wOri=" + wOri + ")";
            }
        };
    }

    private static double rmse3(float[] a, float[] b) {
        double sum = 0.0;
        for (int i = 0; i < 3; i++) {
            double d = a[i] - b[i];
            sum += d * d;
        }
        return Math.sqrt(sum / 3.0);
    }

    private static double rmse3(double[] a, double[] b) {
        double sum = 0.0;
        for (int i = 0; i < 3; i++) {
            double d = a[i] - b[i];
            sum += d * d;
        }
        return Math.sqrt(sum / 3.0);
    }

    /**
     * Quaternion geodesic angle: theta = 2 * acos(|dot(q1,q2)|).
     * Assumes quaternions are in (w,x,y,z).
     */
    private static double quatAngle(float[] q1, float[] q2) {
        double dot = 0.0;
        for (int i = 0; i < 4; i++) dot += q1[i] * q2[i];
        dot = Math.abs(dot);
        dot = Math.min(1.0, Math.max(-1.0, dot));
        return 2.0 * Math.acos(dot);
    }

    private static double quatAngle(double[] q1, double[] q2) {
        double dot = 0.0;
        for (int i = 0; i < 4; i++) dot += q1[i] * q2[i];
        dot = Math.abs(dot);
        dot = Math.min(1.0, Math.max(-1.0, dot));
        return 2.0 * Math.acos(dot);
    }

    private static double clamp01(double v) {
        if (v < 0) return 0;
        if (v > 1) return 1;
        return v;
    }
}
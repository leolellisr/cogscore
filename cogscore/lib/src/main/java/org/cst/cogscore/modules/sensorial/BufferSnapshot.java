/*
 * Click nbfs://nbhost/SystemFileSystem/Templates/Licenses/license-default.txt to change this license
 * Click nbfs://nbhost/SystemFileSystem/Templates/Classes/Class.java to edit this template
 */
package org.modules.sensorial;

/**
 *
 * @author leolellisr
 */
import java.util.Arrays;

/**
 * External snapshot (ground truth) captured at time t0.
 * This is NOT the agent's buffer; it is the reference used for comparison.
 *
 * Type parameter T should be "copyable" (immutable or deep-copiable).
 * For common primitive array buffers (float/double/byte/int and 2D/3D variants),
 * this class provides a convenience deepCopy utility.
 */
public final class BufferSnapshot<T> {

    private final String modality;
    private final long t0Millis;
    private final T groundTruth;

    public BufferSnapshot(String modality, long t0Millis, T groundTruth) {
        if (modality == null) throw new IllegalArgumentException("modality == null");
        if (groundTruth == null) throw new IllegalArgumentException("groundTruth == null");
        this.modality = modality;
        this.t0Millis = t0Millis;
        this.groundTruth = groundTruth;
    }

    public String getModality() {
        return modality;
    }

    public long getT0Millis() {
        return t0Millis;
    }

    public T getGroundTruth() {
        return groundTruth;
    }

    /**
     * Convenience deep copy for typical buffer types.
     * If you use custom buffer objects (e.g., Pose, Quaternion), implement your own copy method
     * and call it before creating the snapshot.
     */
    @SuppressWarnings("unchecked")
    public static <T> T deepCopy(T obj) {
        if (obj == null) return null;

        // 1D primitive arrays
        if (obj instanceof float[]) {
            float[] a = (float[]) obj;
            return (T) Arrays.copyOf(a, a.length);
        }
        if (obj instanceof double[]) {
            double[] a = (double[]) obj;
            return (T) Arrays.copyOf(a, a.length);
        }
        if (obj instanceof int[]) {
            int[] a = (int[]) obj;
            return (T) Arrays.copyOf(a, a.length);
        }
        if (obj instanceof byte[]) {
            byte[] a = (byte[]) obj;
            return (T) Arrays.copyOf(a, a.length);
        }

        // 2D arrays (common for distance/depth maps)
        if (obj instanceof float[][]) {
            float[][] m = (float[][]) obj;
            float[][] copy = new float[m.length][];
            for (int i = 0; i < m.length; i++) {
                copy[i] = Arrays.copyOf(m[i], m[i].length);
            }
            return (T) copy;
        }
        if (obj instanceof double[][]) {
            double[][] m = (double[][]) obj;
            double[][] copy = new double[m.length][];
            for (int i = 0; i < m.length; i++) {
                copy[i] = Arrays.copyOf(m[i], m[i].length);
            }
            return (T) copy;
        }
        if (obj instanceof int[][]) {
            int[][] m = (int[][]) obj;
            int[][] copy = new int[m.length][];
            for (int i = 0; i < m.length; i++) {
                copy[i] = Arrays.copyOf(m[i], m[i].length);
            }
            return (T) copy;
        }
        if (obj instanceof byte[][]) {
            byte[][] m = (byte[][]) obj;
            byte[][] copy = new byte[m.length][];
            for (int i = 0; i < m.length; i++) {
                copy[i] = Arrays.copyOf(m[i], m[i].length);
            }
            return (T) copy;
        }

        // 3D arrays (common for RGB images [H][W][3])
        if (obj instanceof float[][][]) {
            float[][][] t = (float[][][]) obj;
            float[][][] copy = new float[t.length][][];
            for (int i = 0; i < t.length; i++) {
                copy[i] = new float[t[i].length][];
                for (int j = 0; j < t[i].length; j++) {
                    copy[i][j] = Arrays.copyOf(t[i][j], t[i][j].length);
                }
            }
            return (T) copy;
        }
        if (obj instanceof byte[][][]) {
            byte[][][] t = (byte[][][]) obj;
            byte[][][] copy = new byte[t.length][][];
            for (int i = 0; i < t.length; i++) {
                copy[i] = new byte[t[i].length][];
                for (int j = 0; j < t[i].length; j++) {
                    copy[i][j] = Arrays.copyOf(t[i][j], t[i][j].length);
                }
            }
            return (T) copy;
        }

        // Fallback: if the object is immutable, returning as-is is fine.
        // If it is mutable and not supported here, you MUST provide your own deep copy.
        return obj;
    }
}
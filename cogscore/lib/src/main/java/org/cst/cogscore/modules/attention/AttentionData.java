package org.cst.cogscore.modules.attention;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public final class AttentionData {

    public AttentionData() {
    }

    public enum CueType {
        ENDOGENOUS,
        EXOGENOUS,
        NEUTRAL
    }

    public enum TrialType {
        VALID,
        INVALID,
        NEUTRAL,
        UNDEFINED
    }

    public enum SearchType {
        NONE,
        FEATURE,
        CONJUNCTION
    }

    public static final class Point implements Serializable {
        private static final long serialVersionUID = 1L;

        private final double x;
        private final double y;

        public Point(double x, double y) {
            this.x = clamp01(x);
            this.y = clamp01(y);
        }

        public static Point fromCell(int x, int y, int width, int height) {
            double nx;
            double ny;

            if (width <= 1) nx = 0.5;
            else nx = ((double) x) / (double) (width - 1);

            if (height <= 1) ny = 0.5;
            else ny = ((double) y) / (double) (height - 1);

            return new Point(nx, ny);
        }

        private static double clamp01(double v) {
            if (Double.isNaN(v)) return 0.0;
            if (v < 0.0) return 0.0;
            if (v > 1.0) return 1.0;
            return v;
        }

        public double getX() {
            return x;
        }

        public double getY() {
            return y;
        }

        @Override
        public String toString() {
            return "Point{x=" + x + ", y=" + y + "}";
        }
    }

    public static final class Frame implements Serializable {
        private static final long serialVersionUID = 1L;

        private final long cycle;
        private final double[][] map;

        public Frame(long cycle, double[][] map) {
            validateMap(map);
            this.cycle = cycle;
            this.map = deepCopy(map);
        }

        public long getCycle() {
            return cycle;
        }

        public int getWidth() {
            return map[0].length;
        }

        public int getHeight() {
            return map.length;
        }

        public double[][] getMapCopy() {
            return deepCopy(map);
        }

        public double getValue(int x, int y) {
            return map[y][x];
        }

        public double getValueAtNormalized(Point p) {
            int x = normalizedToCellX(p.getX(), getWidth());
            int y = normalizedToCellY(p.getY(), getHeight());
            return map[y][x];
        }

        public int[] getPeakCell() {
            int bestX = 0;
            int bestY = 0;
            double best = map[0][0];

            for (int y = 0; y < map.length; y++) {
                for (int x = 0; x < map[y].length; x++) {
                    if (map[y][x] > best) {
                        best = map[y][x];
                        bestX = x;
                        bestY = y;
                    }
                }
            }
            return new int[]{bestX, bestY};
        }

        public Point getPeakNormalized() {
            int[] cell = getPeakCell();
            return Point.fromCell(cell[0], cell[1], getWidth(), getHeight());
        }

        public double getPeakValue() {
            int[] cell = getPeakCell();
            return map[cell[1]][cell[0]];
        }

        public double variance() {
            int h = getHeight();
            int w = getWidth();
            int n = h * w;

            double sum = 0.0;
            double sumSq = 0.0;

            for (int y = 0; y < h; y++) {
                for (int x = 0; x < w; x++) {
                    double v = map[y][x];
                    sum += v;
                    sumSq += v * v;
                }
            }

            double mean = sum / (double) n;
            double var = (sumSq / (double) n) - (mean * mean);
            return Math.max(0.0, var);
        }

        public double normalizedEntropy() {
            int h = getHeight();
            int w = getWidth();
            int n = h * w;

            double sumPositive = 0.0;
            for (int y = 0; y < h; y++) {
                for (int x = 0; x < w; x++) {
                    double v = map[y][x];
                    if (v > 0.0) sumPositive += v;
                }
            }

            if (sumPositive <= 0.0) {
                return 1.0;
            }

            double entropy = 0.0;
            for (int y = 0; y < h; y++) {
                for (int x = 0; x < w; x++) {
                    double v = map[y][x];
                    if (v > 0.0) {
                        double p = v / sumPositive;
                        entropy -= p * Math.log(p);
                    }
                }
            }

            double maxEntropy = Math.log((double) n);
            if (maxEntropy <= 0.0) return 1.0;

            return entropy / maxEntropy;
        }

        private static int normalizedToCellX(double nx, int width) {
            if (width <= 1) return 0;
            int x = (int) Math.round(nx * (double) (width - 1));
            if (x < 0) return 0;
            if (x >= width) return width - 1;
            return x;
        }

        private static int normalizedToCellY(double ny, int height) {
            if (height <= 1) return 0;
            int y = (int) Math.round(ny * (double) (height - 1));
            if (y < 0) return 0;
            if (y >= height) return height - 1;
            return y;
        }

        private static void validateMap(double[][] map) {
            if (map == null || map.length == 0 || map[0] == null || map[0].length == 0) {
                throw new IllegalArgumentException("Attention map cannot be null or empty");
            }

            int width = map[0].length;
            for (int y = 0; y < map.length; y++) {
                if (map[y] == null || map[y].length != width) {
                    throw new IllegalArgumentException("Attention map must be rectangular");
                }
            }
        }

        private static double[][] deepCopy(double[][] src) {
            double[][] copy = new double[src.length][];
            for (int i = 0; i < src.length; i++) {
                copy[i] = new double[src[i].length];
                System.arraycopy(src[i], 0, copy[i], 0, src[i].length);
            }
            return copy;
        }
    }

    public static final class TrialInput implements Serializable {
        private static final long serialVersionUID = 1L;

        public String trialId = "";
        public int episode = 0;
        public CueType cueType = CueType.NEUTRAL;
        public TrialType trialType = TrialType.UNDEFINED;
        public SearchType searchType = SearchType.NONE;

        public Point targetNormalized = null;
        public Point cueNormalized = null;
        public Point fixationNormalized = new Point(0.5, 0.5);
        public double targetRadiusNormalized = 0.10;

        public String modality = "attention";
        public final List<Frame> frames = new ArrayList<Frame>();

        public Long cueOnsetCycle = null;
        public Long targetOnsetCycle = null;
        public Long externalDetectionCycle = null;
        public Long overtMovementCycle = null;
        public Double soaMs = null;

        public Boolean overtMovementEnabled = null;
        public Integer distractorCount = null;
        public Boolean flanked = null;
        public Double flankerDistance = null;

        public int mapWidth = 0;
        public int mapHeight = 0;

        public TrialInput setTrialId(String trialId) {
            this.trialId = trialId;
            return this;
        }

        public TrialInput setEpisode(int episode) {
            this.episode = episode;
            return this;
        }

        public TrialInput setCueType(CueType cueType) {
            this.cueType = cueType == null ? CueType.NEUTRAL : cueType;
            return this;
        }

        public TrialInput setTrialType(TrialType trialType) {
            this.trialType = trialType == null ? TrialType.UNDEFINED : trialType;
            return this;
        }

        public TrialInput setSearchType(SearchType searchType) {
            this.searchType = searchType == null ? SearchType.NONE : searchType;
            return this;
        }

        public TrialInput setTargetNormalized(Point targetNormalized) {
            this.targetNormalized = targetNormalized;
            return this;
        }

        public TrialInput setCueNormalized(Point cueNormalized) {
            this.cueNormalized = cueNormalized;
            return this;
        }

        public TrialInput setFixationNormalized(Point fixationNormalized) {
            this.fixationNormalized = fixationNormalized == null ? new Point(0.5, 0.5) : fixationNormalized;
            return this;
        }

        public TrialInput setTargetRadiusNormalized(double targetRadiusNormalized) {
            this.targetRadiusNormalized = targetRadiusNormalized;
            return this;
        }

        public TrialInput setModality(String modality) {
            this.modality = modality;
            return this;
        }

        public TrialInput setCueOnsetCycle(Long cueOnsetCycle) {
            this.cueOnsetCycle = cueOnsetCycle;
            return this;
        }

        public TrialInput setTargetOnsetCycle(Long targetOnsetCycle) {
            this.targetOnsetCycle = targetOnsetCycle;
            return this;
        }

        public TrialInput setExternalDetectionCycle(Long externalDetectionCycle) {
            this.externalDetectionCycle = externalDetectionCycle;
            return this;
        }

        public TrialInput setOvertMovementCycle(Long overtMovementCycle) {
            this.overtMovementCycle = overtMovementCycle;
            return this;
        }

        public TrialInput setSoaMs(Double soaMs) {
            this.soaMs = soaMs;
            return this;
        }

        public TrialInput setOvertMovementEnabled(Boolean overtMovementEnabled) {
            this.overtMovementEnabled = overtMovementEnabled;
            return this;
        }

        public TrialInput setDistractorCount(Integer distractorCount) {
            this.distractorCount = distractorCount;
            return this;
        }

        public TrialInput setFlanked(Boolean flanked) {
            this.flanked = flanked;
            return this;
        }

        public TrialInput setFlankerDistance(Double flankerDistance) {
            this.flankerDistance = flankerDistance;
            return this;
        }

        public TrialInput setMapDimensions(int mapWidth, int mapHeight) {
            this.mapWidth = mapWidth;
            this.mapHeight = mapHeight;
            return this;
        }

        public TrialInput addFrame(Frame frame) {
            if (frame != null) {
                this.frames.add(frame);
                this.mapWidth = frame.getWidth();
                this.mapHeight = frame.getHeight();
            }
            return this;
        }

        public TrialInput addFrame(long cycle, double[][] map) {
            Frame frame = new Frame(cycle, map);
            this.frames.add(frame);
            this.mapWidth = frame.getWidth();
            this.mapHeight = frame.getHeight();
            return this;
        }

        public TrialInput setSingleMap(double[][] map) {
            this.frames.clear();
            return addFrame(0L, map);
        }

        public boolean isValid() {
            return targetNormalized != null && targetOnsetCycle != null && !frames.isEmpty();
        }

        public Frame getFirstFrame() {
            if (frames.isEmpty()) {
                throw new IllegalStateException("TrialInput has no frames");
            }
            return frames.get(0);
        }

        public Frame getLastFrame() {
            if (frames.isEmpty()) {
                throw new IllegalStateException("TrialInput has no frames");
            }
            return frames.get(frames.size() - 1);
        }

        public List<Frame> getFramesReadOnly() {
            return Collections.unmodifiableList(frames);
        }
    }
}
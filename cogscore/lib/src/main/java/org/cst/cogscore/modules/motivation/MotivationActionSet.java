package org.cst.cogscore.modules.motivation;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public final class MotivationActionSet {

    private MotivationActionSet() {
    }

    public enum Category {
        MOTOR(1),
        VIRTUAL(2),
        ATTENTIONAL(3);

        public final int code;

        Category(int code) {
            this.code = code;
        }
    }

    public enum FunctionalType {
        NONE(0),
        LOOK(1),
        INTERACT(2),
        STOP(3);

        public final int code;

        FunctionalType(int code) {
            this.code = code;
        }

        public static FunctionalType fromCode(int code) {
            for (FunctionalType t : values()) {
                if (t.code == code) {
                    return t;
                }
            }
            return NONE;
        }

        public static FunctionalType fromString(String raw) {
            if (raw == null) {
                return NONE;
            }

            String s = raw.trim().toUpperCase();

            if ("LOOK".equals(s) || "INSPECT".equals(s) || "FIXATE".equals(s)) {
                return LOOK;
            }

            if ("INTERACT".equals(s) || "TOUCH".equals(s) || "MANIPULATE".equals(s)) {
                return INTERACT;
            }

            if ("STOP".equals(s) || "OMIT".equals(s)) {
                return STOP;
            }

            try {
                return fromCode(Integer.parseInt(s));
            } catch (NumberFormatException ignored) {
                return NONE;
            }
        }
    }

    public enum ActionId implements Serializable {
        AM0(0, "AM0", "Keep Focus", Category.MOTOR, 1),
        AM1(1, "AM1", "Neck to Left", Category.MOTOR, 1),
        AM2(2, "AM2", "Neck to Right", Category.MOTOR, 1),
        AM3(3, "AM3", "Head Up", Category.MOTOR, 1),
        AM4(4, "AM4", "Head Down", Category.MOTOR, 1),

        AM5(5, "AM5", "Fovea 0", Category.VIRTUAL, 1),
        AM6(6, "AM6", "Fovea 1", Category.VIRTUAL, 1),
        AM7(7, "AM7", "Fovea 2", Category.VIRTUAL, 1),
        AM8(8, "AM8", "Fovea 3", Category.VIRTUAL, 1),
        AM9(9, "AM9", "Fovea 4", Category.VIRTUAL, 1),

        AM10(10, "AM10", "Neck to Focus", Category.MOTOR, 1),
        AM11(11, "AM11", "Head to Focus", Category.MOTOR, 1),
        AM12(12, "AM12", "Neck away from Focus", Category.MOTOR, 1),
        AM13(13, "AM13", "Head away from Focus", Category.MOTOR, 1),

        AM14(14, "AM14", "Interact with Red Object", Category.MOTOR, 1),
        AM15(15, "AM15", "Interact with Green Object", Category.MOTOR, 1),
        AM16(16, "AM16", "Interact with Blue Object", Category.MOTOR, 1),

        AA0(17, "AA0", "Define desired color as focus", Category.ATTENTIONAL, 3),
        AA1(18, "AA1", "Define desired distance as focus", Category.ATTENTIONAL, 3),
        AA2(19, "AA2", "Define desired region as focus", Category.ATTENTIONAL, 3);

        public final int code;
        public final String id;
        public final String label;
        public final Category category;
        public final int introducedPhase;

        ActionId(int code, String id, String label, Category category, int introducedPhase) {
            this.code = code;
            this.id = id;
            this.label = label;
            this.category = category;
            this.introducedPhase = introducedPhase;
        }

        public static ActionId fromCode(int code) {
            for (ActionId a : values()) {
                if (a.code == code) {
                    return a;
                }
            }
            return null;
        }

        public static ActionId fromString(String raw) {
            if (raw == null) {
                return null;
            }

            String s = raw.trim().toUpperCase();

            if (s.isEmpty()) {
                return null;
            }

            for (ActionId a : values()) {
                if (a.id.equals(s) || a.name().equals(s)) {
                    return a;
                }
            }

            try {
                return fromCode(Integer.parseInt(s));
            } catch (NumberFormatException ignored) {
                return null;
            }
        }
    }

    public static boolean isAvailableInPhase(ActionId action, int phase) {
        if (action == null) {
            return false;
        }

        return phase >= action.introducedPhase;
    }

    public static int availableActionCountForPhase(int phase) {
        int n = 0;

        for (ActionId a : ActionId.values()) {
            if (isAvailableInPhase(a, phase)) {
                n++;
            }
        }

        return n;
    }

    public static List<ActionId> availableActionsForPhase(int phase) {
        List<ActionId> out = new ArrayList<ActionId>();

        for (ActionId a : ActionId.values()) {
            if (isAvailableInPhase(a, phase)) {
                out.add(a);
            }
        }

        return Collections.unmodifiableList(out);
    }

    public static FunctionalType defaultFunctionalType(ActionId action, int resolvedObjectIndex) {
        if (action == null) {
            return FunctionalType.NONE;
        }

        switch (action) {
            case AM14:
            case AM15:
            case AM16:
                return resolvedObjectIndex > 0 ? FunctionalType.INTERACT : FunctionalType.NONE;

            case AM0:
            case AM5:
            case AM6:
            case AM7:
            case AM8:
            case AM9:
            case AM10:
            case AM11:
            case AA0:
            case AA1:
            case AA2:
                return resolvedObjectIndex > 0 ? FunctionalType.LOOK : FunctionalType.NONE;

            case AM1:
            case AM2:
            case AM3:
            case AM4:
                return resolvedObjectIndex > 0 ? FunctionalType.LOOK : FunctionalType.NONE;

            case AM12:
            case AM13:
                return FunctionalType.NONE;

            default:
                return FunctionalType.NONE;
        }
    }
}



package com.base.crules;

import java.util.HashMap;
import java.util.Map;

/** JNI declarations required by the Bilibili SDK security-header library. */
public final class CustomRules {
    public static long ref;
    private final IProvider mProvider;

    public CustomRules(IProvider provider) { mProvider = provider; }

    public interface IProvider {
        String getRule();
        int getVersion();
        String getUdid();
        String getCdid();
        String getID();
        String getDeviceInfo();
    }

    public native Map<String, String> getTokens(HashMap<String, String> values);
    public String a(String left, String right) { return ref + ";" + left + ";" + right; }
    public long b(int value) { return ref + value; }
    public long c(int value) { return ref % value; }
}

// Copyright Aociety. All rights reserved.
#include "../AocietyRequestJson.h"
#include "../AocietyConversationScope.h"
#include "../AocietyDialogueValidation.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Serialization/JsonReader.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FAocietyRequestEscapingTest,
    "Aociety.Network.JsonControlCharacterRoundTrip",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FAocietyRequestEscapingTest::RunTest(const FString& Parameters)
{
    const FString Input = TEXT("你好\n第二行\t\"quoted\" C:\\folder\\file\r");
    const TSharedRef<FJsonObject> Object = MakeShared<FJsonObject>();
    Object->SetStringField(TEXT("player_input"), Input);
    Object->SetStringField(TEXT("npc_id"), TEXT("npc_01"));
    const FString Body = AocietyRequestJson::Serialize(Object);
    TSharedPtr<FJsonObject> Parsed;
    TestTrue(TEXT("Serialized body parses"),
        FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Body), Parsed));
    if (!Parsed.IsValid()) return false;
    FString RoundTrip;
    TestTrue(TEXT("Input is a string"), Parsed->TryGetStringField(TEXT("player_input"), RoundTrip));
    TestEqual(TEXT("All control characters and Unicode preserved"), RoundTrip, Input);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FAocietyNestedRequestEscapingTest,
    "Aociety.Network.JsonNestedPayloadRoundTrip",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FAocietyNestedRequestEscapingTest::RunTest(const FString& Parameters)
{
    const FString Key = TEXT("quoted\"key");
    const FString Value = TEXT("森林\n小镇\\雪");
    const TSharedRef<FJsonObject> Payload = MakeShared<FJsonObject>();
    Payload->SetStringField(Key, Value);
    const TSharedRef<FJsonObject> Object = MakeShared<FJsonObject>();
    Object->SetObjectField(TEXT("payload"), Payload);
    TSharedPtr<FJsonObject> Parsed;
    TestTrue(TEXT("Nested request body parses"), FJsonSerializer::Deserialize(
        TJsonReaderFactory<>::Create(AocietyRequestJson::Serialize(Object)), Parsed));
    if (!Parsed.IsValid()) return false;
    const TSharedPtr<FJsonObject>* ParsedPayload = nullptr;
    TestTrue(TEXT("Payload remains an object"), Parsed->TryGetObjectField(TEXT("payload"), ParsedPayload));
    if (!ParsedPayload || !ParsedPayload->IsValid()) return false;
    FString RoundTrip;
    TestTrue(TEXT("Quoted key preserved"), (*ParsedPayload)->TryGetStringField(Key, RoundTrip));
    TestEqual(TEXT("Nested value preserved"), RoundTrip, Value);
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FAocietyConversationScopeTest,
    "Aociety.Network.ConversationIdentityIsolation",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FAocietyConversationScopeTest::RunTest(const FString& Parameters)
{
    const FString First = AocietyConversationScope::GetNamespace(TEXT("account-one"), TEXT("agent-one"));
    TestEqual(TEXT("Namespace is stable"), First,
        AocietyConversationScope::GetNamespace(TEXT("account-one"), TEXT("agent-one")));
    TestNotEqual(TEXT("Different account isolated"), First,
        AocietyConversationScope::GetNamespace(TEXT("account-two"), TEXT("agent-one")));
    TestNotEqual(TEXT("Different Agent isolated"), First,
        AocietyConversationScope::GetNamespace(TEXT("account-one"), TEXT("agent-two")));
    TestNotEqual(TEXT("Unicode identities remain distinct"),
        AocietyConversationScope::GetNamespace(TEXT("居民甲"), TEXT("agent")),
        AocietyConversationScope::GetNamespace(TEXT("居民乙"), TEXT("agent")));
    const FString UnsafeInput = AocietyConversationScope::GetNamespace(TEXT("../../account"), TEXT("C:\\agent"));
    TestEqual(TEXT("Path component has a bounded length"), UnsafeInput.Len(), 32);
    TestFalse(TEXT("Input cannot insert path separators"), UnsafeInput.Contains(TEXT("/")) || UnsafeInput.Contains(TEXT("\\")));
#if UE_BUILD_SHIPPING
    TestTrue(TEXT("Missing Shipping identity has no namespace"),
        AocietyConversationScope::GetNamespace(TEXT(""), TEXT("")).IsEmpty());
#else
    TestEqual(TEXT("Unauthenticated development is explicitly isolated"),
        AocietyConversationScope::GetNamespace(TEXT(""), TEXT("")), FString(TEXT("development-local")));
#endif
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FAocietyDialogueMetadataTest,
    "Aociety.Network.DialogueMetadataMustBeExplicit",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FAocietyDialogueMetadataTest::RunTest(const FString& Parameters)
{
    const auto MakeValid = []()
    {
        const TSharedRef<FJsonObject> Object = MakeShared<FJsonObject>();
        Object->SetStringField(TEXT("npc_id"), TEXT("npc_01"));
        Object->SetStringField(TEXT("source"), TEXT("llm"));
        Object->SetStringField(TEXT("model"), TEXT("deepseek-v4-flash"));
        Object->SetStringField(TEXT("provider"), TEXT("deepseek"));
        Object->SetStringField(TEXT("mode"), TEXT("player"));
        Object->SetStringField(TEXT("counterpart_id"), TEXT(""));
        return Object;
    };
    AocietyDialogueValidation::FMetadata Metadata;
    TSharedPtr<FJsonObject> Payload;
    TestTrue(TEXT("Explicit metadata parses"), AocietyDialogueValidation::TryReadMetadata(MakeValid(), Metadata, Payload));
    TestTrue(TEXT("Canonical provider/model verifies"), AocietyDialogueValidation::IsVerifiedLLM(Metadata));
    TestTrue(TEXT("Player request routing matches"), AocietyDialogueValidation::MatchesRequest(
        Metadata, TEXT("npc_01"), TEXT("player"), TEXT("")));
    TestFalse(TEXT("Wrong NPC rejected"), AocietyDialogueValidation::MatchesRequest(
        Metadata, TEXT("npc_02"), TEXT("player"), TEXT("")));
    TestFalse(TEXT("Wrong mode rejected"), AocietyDialogueValidation::MatchesRequest(
        Metadata, TEXT("npc_01"), TEXT("ambient"), TEXT("")));
    TestFalse(TEXT("Wrong counterpart rejected"), AocietyDialogueValidation::MatchesRequest(
        Metadata, TEXT("npc_01"), TEXT("player"), TEXT("npc_02")));
    for (const TCHAR* Field : { TEXT("npc_id"), TEXT("source"), TEXT("model"), TEXT("provider"), TEXT("mode"), TEXT("counterpart_id") })
    {
        TSharedRef<FJsonObject> Object = MakeValid();
        Object->RemoveField(Field);
        TestFalse(FString::Printf(TEXT("Missing %s rejected"), Field),
            AocietyDialogueValidation::TryReadMetadata(Object, Metadata, Payload));
        Object = MakeValid();
        Object->SetNumberField(Field, 1);
        TestFalse(FString::Printf(TEXT("Wrong type for %s rejected"), Field),
            AocietyDialogueValidation::TryReadMetadata(Object, Metadata, Payload));
    }
    TSharedRef<FJsonObject> Root = MakeValid();
    const TSharedRef<FJsonObject> Partial = MakeShared<FJsonObject>();
    Partial->SetStringField(TEXT("source"), TEXT("llm"));
    Root->SetObjectField(TEXT("dialogue"), Partial);
    TestFalse(TEXT("Partial nested payload cannot inherit root metadata"),
        AocietyDialogueValidation::TryReadMetadata(Root, Metadata, Payload));
    Root->SetStringField(TEXT("dialogue"), TEXT("invalid-object"));
    TestFalse(TEXT("Wrong nested object type rejected"),
        AocietyDialogueValidation::TryReadMetadata(Root, Metadata, Payload));
    Root->SetObjectField(TEXT("dialogue"), MakeValid());
    TestTrue(TEXT("Complete nested payload accepted"),
        AocietyDialogueValidation::TryReadMetadata(Root, Metadata, Payload));
    Metadata.Provider = TEXT("other");
    TestFalse(TEXT("Other provider never verifies"), AocietyDialogueValidation::IsVerifiedLLM(Metadata));
    Metadata.Provider = TEXT("deepseek");
    Metadata.Model = TEXT("unknown-model");
    TestFalse(TEXT("Unknown model never verifies"), AocietyDialogueValidation::IsVerifiedLLM(Metadata));
    return true;
}
#endif

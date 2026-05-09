from __future__ import annotations

import unittest

from contract_helpers import load_demo_semantic_pack


class JoinRecipeContractTest(unittest.TestCase):
    def test_demo_pack_join_recipes_are_explicit_and_recommended(self) -> None:
        pack = load_demo_semantic_pack()
        joins = {join["id"]: join for join in pack["join_recipes"]}
        self.assertIn("join.users_payments", joins)
        self.assertIn("join.payments_campaigns", joins)
        self.assertEqual(joins["join.users_payments"]["condition"], "users.user_id = payments.user_id")
        self.assertEqual(joins["join.payments_campaigns"]["condition"], "payments.campaign_id = campaigns.campaign_id")
        for join in joins.values():
            self.assertIn(join["join_type"], {"many_to_one", "one_to_one", "one_to_many", "many_to_many"})
            self.assertIs(join["recommended"], True)
            self.assertTrue(join["warnings"])

    def test_users_payments_join_recipe_contract_shape(self) -> None:
        users_payments_join_recipe = {
            "id": "join.users_payments",
            "left_table": "users",
            "right_table": "payments",
            "join_type": "one_to_many",
            "condition": "users.user_id = payments.user_id",
            "recommended": True,
            "warnings": ["Join on stable user_id only; never join on email or phone."],
        }
        self.assertEqual(users_payments_join_recipe["id"], "join.users_payments")
        self.assertEqual(users_payments_join_recipe["condition"], "users.user_id = payments.user_id")
        self.assertTrue(users_payments_join_recipe["recommended"])
        self.assertIn("email", users_payments_join_recipe["warnings"][0])

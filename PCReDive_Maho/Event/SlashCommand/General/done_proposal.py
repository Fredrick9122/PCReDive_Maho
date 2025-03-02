import datetime
from discord_slash.utils.manage_commands import create_option, create_choice
import Discord_client
import Module.DB_control
import Module.Update
import Module.info_update
import Module.define_value

@Discord_client.slash.slash( 
             name="d" ,
             description="出刀回報，當出完刀表上的某一刀時使用",
             options= [
                 create_option(
                     name="序號",
                     description="請查看刀表，填入該刀在刀表中的序號",
                     option_type=4,
                     required=True
                 ),
                 create_option(
                     name="類型",
                     description="是正刀、尾刀、還是補償刀?",
                     option_type=4,
                     required=True,
                     choices=[
                         create_choice(name="正刀", value=1),create_choice(name="尾刀", value=2),create_choice(name="補償刀", value=3)
                         # value = 0 為一般報刀使用，無法統計刀數
                         # 尾刀出完扣除0.5
                         # 補償刀出完扣除0.5
                     ]
                 ),
                  create_option(
                     name="傷害",
                     description="實際打了多少血，僅能輸入數字",
                     option_type=4,
                     required=True
                 )
             ],
             connector={"序號": "index", "類型": "knife_type", "傷害": "real_damage"}
             )
async def done_proposal(ctx, index, knife_type, real_damage):
  connection = await Module.DB_control.OpenConnection(ctx)
  if connection:
    cursor = connection.cursor(prepared=True)
    sql = "SELECT now_week, now_boss, week_offset, group_serial, policy FROM princess_connect.group WHERE server_id = ? and sign_channel_id = ? order by group_serial limit 0, 1"
    data = (ctx.guild.id, ctx.channel.id)
    cursor.execute(sql, data) # 認證身分
    row = cursor.fetchone()
    cursor.close
    if row:
      now_week = row[0]
      now_boss = row[1]
      group_serial = row[3]
      policy = row[4]
      if policy == Module.define_value.Policy.YES.value:
        if index > 0:
          # 尋找該刀
          cursor = connection.cursor(prepared=True)
          sql = "SELECT serial_number,member_id from princess_connect.knifes where server_id=? and group_serial=? and week=? and boss=? order by serial_number limit ?,1"
          data = (ctx.guild.id, group_serial, now_week, now_boss, index-1)
          cursor.execute(sql, data)
          row = cursor.fetchone()
          cursor.close()
          if row:
            if ctx.author.id == row[1]:
              cursor = connection.cursor(prepared=True)
              sql = "UPDATE princess_connect.knifes set real_damage=?, knife_type=?, done_time=? where serial_number=?"
              data = (real_damage, knife_type, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), row[0])
              row = cursor.execute(sql, data)
              cursor.close()
              connection.commit()
              await ctx.send('回報成功!')
              await Module.Update.Update(ctx, ctx.guild.id, group_serial) # 更新刀表
              await Module.info_update.info_update(ctx ,ctx.guild.id, group_serial) # 更新資訊
            else:
              await ctx.send('您並非該刀主人喔!')
          else:
            await ctx.send('該刀不存在喔!')
        else:
          await ctx.send('序號必須大於0!')
      else:
        await ctx.send('目前戰隊政策為:**不回報傷害**! 指令無效，感謝你的自主回報!')
        
    else:
      await ctx.send('這裡不是報刀頻道喔!')
    await Module.DB_control.CloseConnection(connection, ctx)